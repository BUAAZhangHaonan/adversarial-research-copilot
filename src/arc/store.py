"""SQLite is authoritative; immutable artifacts and Markdown are views."""
from __future__ import annotations
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
from urllib.parse import urlsplit, urlunsplit

from pydantic import BaseModel
from .schemas import (Campaign, RunRecord, ResearchCard, CardDraft, SourceRecord,
    EvidenceRecord, TaskRecord, Issue, IssueTransition, DirectionChange,
    DirectionChangeDraft, SelectorResult, Finding, utc_now, stable_id)

class StateError(RuntimeError):
    pass

def _dump(value):
    if isinstance(value, BaseModel):
        return value.model_dump_json()
    def encode(item):
        if isinstance(item,BaseModel): return item.model_dump(mode="json")
        raise TypeError("unsupported_state_value")
    return json.dumps(value, ensure_ascii=False, sort_keys=True,default=encode)

def claim_fingerprint(claim):
    """Identify the target claim content, independent of its evidence links."""
    from .schemas import Claim
    claim=Claim.model_validate(claim)
    return hashlib.sha256(_dump(claim.model_dump(exclude={"evidence_ids"})).encode("utf-8")).hexdigest()

def _tokens(text):
    """Latin terms and overlapping CJK bigrams; retrieval only, never judgment."""
    latin = re.findall(r"[a-z0-9_]+", text.casefold())
    cjk = re.findall(r"[\u3400-\u9fff]+", text)
    return list(dict.fromkeys(latin + [word[i:i+2] for word in cjk for i in range(max(1,len(word)-1))]))

def canonical_source(source):
    if source.doi:
        return "doi:" + source.doi.lower().removeprefix("https://doi.org/").strip()
    arxiv = source.arxiv_id
    if not arxiv and source.url:
        found = re.search(r"arxiv\.org/(?:abs|pdf|html)/([^?#]+)", source.url)
        if found:
            arxiv = found[1].removesuffix(".pdf")
    if arxiv:
        return "arxiv:" + re.sub(r"v\d+$", "", arxiv.removeprefix("arXiv:").strip())
    if source.url:
        parsed = urlsplit(source.url)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password:
            raise StateError("invalid_source_url")
        return urlunsplit((parsed.scheme.lower(), parsed.netloc.lower(), parsed.path.rstrip("/"), parsed.query, ""))
    if source.source_type != "user_material":
        raise StateError("source_identifier_required")
    return "user:" + (source.canonical_id or source.source_id)

class Store:
    def __init__(self, db_path, artifact_root=None):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.artifact_root = Path(artifact_root or self.db_path.parent / "artifacts").resolve()
        self.artifact_root.mkdir(parents=True, exist_ok=True)
        if os.name != "nt":
            os.chmod(self.artifact_root, 0o700)
        with self._connect() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS campaigns(id TEXT PRIMARY KEY,data TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS runs(id TEXT PRIMARY KEY,campaign_id TEXT REFERENCES campaigns(id),data TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS draws(id TEXT PRIMARY KEY,campaign_id TEXT NOT NULL REFERENCES campaigns(id),ordinal INTEGER NOT NULL,started_at TEXT NOT NULL,UNIQUE(campaign_id,ordinal));
                CREATE TABLE IF NOT EXISTS cards(card_id TEXT NOT NULL,version INTEGER NOT NULL,data TEXT NOT NULL,PRIMARY KEY(card_id,version));
                CREATE TABLE IF NOT EXISTS card_creation(creation_key TEXT PRIMARY KEY,card_id TEXT NOT NULL,version INTEGER NOT NULL,input_hash TEXT NOT NULL,FOREIGN KEY(card_id,version) REFERENCES cards(card_id,version));
                CREATE TABLE IF NOT EXISTS run_cards(run_id TEXT NOT NULL REFERENCES runs(id),card_id TEXT NOT NULL,version INTEGER NOT NULL,PRIMARY KEY(run_id,card_id,version),FOREIGN KEY(card_id,version) REFERENCES cards(card_id,version));
                CREATE TABLE IF NOT EXISTS selections(card_id TEXT NOT NULL,version INTEGER NOT NULL,run_id TEXT REFERENCES runs(id),data TEXT NOT NULL,PRIMARY KEY(card_id,version),FOREIGN KEY(card_id,version) REFERENCES cards(card_id,version));
                CREATE TABLE IF NOT EXISTS sources(id TEXT PRIMARY KEY,canonical_id TEXT NOT NULL,version TEXT NOT NULL,origin TEXT NOT NULL,data TEXT NOT NULL);
                CREATE UNIQUE INDEX IF NOT EXISTS source_representation_identity ON sources(canonical_id,version,origin,COALESCE(json_extract(data,'$.representation_id'),''));
                CREATE TABLE IF NOT EXISTS evidence(id TEXT PRIMARY KEY,source_id TEXT NOT NULL REFERENCES sources(id),run_id TEXT,data TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS tasks(id TEXT PRIMARY KEY,run_id TEXT NOT NULL REFERENCES runs(id),data TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS issues(run_id TEXT NOT NULL REFERENCES runs(id),id TEXT NOT NULL,data TEXT NOT NULL,PRIMARY KEY(run_id,id));
                CREATE TABLE IF NOT EXISTS issue_events(event_id INTEGER PRIMARY KEY AUTOINCREMENT,run_id TEXT NOT NULL,data TEXT NOT NULL,created_at TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS issue_applied(event_key TEXT PRIMARY KEY,run_id TEXT NOT NULL,input_hash TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS direction_changes(id TEXT PRIMARY KEY,run_id TEXT NOT NULL REFERENCES runs(id),data TEXT NOT NULL,audit TEXT NOT NULL);
                CREATE UNIQUE INDEX IF NOT EXISTS one_direction_per_run ON direction_changes(run_id);
                CREATE TABLE IF NOT EXISTS capabilities(id TEXT PRIMARY KEY,run_id TEXT NOT NULL REFERENCES runs(id),data TEXT NOT NULL);
                CREATE VIRTUAL TABLE IF NOT EXISTS archive_fts USING fts5(card_id UNINDEXED,version UNINDEXED,body);
            """)
        if os.name != "nt":
            os.chmod(self.db_path, 0o600)

    def _connect(self):
        db = sqlite3.connect(self.db_path, timeout=30)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        db.execute("PRAGMA busy_timeout=30000")
        return db

    @contextmanager
    def _transaction(self):
        db = self._connect()
        try:
            db.execute("BEGIN IMMEDIATE")
            yield db
            db.commit()
        except BaseException:
            db.rollback()
            raise
        finally:
            db.close()

    def _artifact_path(self, relative_path):
        candidate = self.artifact_root / relative_path
        resolved = candidate.resolve()
        if not resolved.is_relative_to(self.artifact_root) or resolved == self.artifact_root:
            raise StateError("artifact_path_outside_root")
        return resolved

    def save_artifact(self, relative_path, content):
        logical_target = self._artifact_path(relative_path)
        target = self._filesystem_path(logical_target)
        target.parent.mkdir(parents=True, exist_ok=True)
        temp = target.with_name(stable_id("tmp"))
        blob = content.encode("utf-8") if isinstance(content, str) else content
        try:
            with temp.open("xb") as output:
                if os.name != "nt":
                    os.chmod(temp, 0o600)
                output.write(blob)
                output.flush()
                os.fsync(output.fileno())
            os.replace(temp, target)
        finally:
            if temp.exists():
                temp.unlink()
        return str(logical_target.relative_to(self.artifact_root)).replace("\\", "/")

    @staticmethod
    def _filesystem_path(path):
        # Windows extended-length syntax changes only OS access, never stored IDs
        # or the resolved containment check above.
        if os.name == "nt":
            raw=str(path)
            if raw.startswith("\\\\?\\"):
                return path
            return Path("\\\\?\\UNC\\"+raw[2:] if raw.startswith("\\\\") else "\\\\?\\"+raw)
        return path

    def read_artifact(self, relative_path):
        return self._filesystem_path(self._artifact_path(relative_path)).read_text(encoding="utf-8")

    def create_campaign(self, topic, boundaries=None, max_draws=5, budget_account_id=None, campaign_id=None, parent_card_id=None, parent_card_version=None):
        record = Campaign(campaign_id=campaign_id or stable_id("campaign"),topic=topic,boundaries=boundaries or [],max_draws=max_draws,budget_account_id=budget_account_id,parent_card_id=parent_card_id,parent_card_version=parent_card_version)
        if parent_card_id:
            self.get_card(parent_card_id,parent_card_version)
        with self._transaction() as db:
            db.execute("INSERT INTO campaigns VALUES (?,?)", (record.campaign_id,_dump(record)))
        return record

    def get_campaign(self, campaign_id):
        with self._connect() as db:
            row=db.execute("SELECT data FROM campaigns WHERE id=?",(campaign_id,)).fetchone()
        if row is None:
            raise StateError("campaign_missing")
        return Campaign.model_validate_json(row[0])

    def update_campaign(self,campaign_id,**changes):
        if set(changes)-{"retained_families","source_ids"}:
            raise StateError("campaign_identity_or_quota_immutable")
        with self._transaction() as db:
            row=db.execute("SELECT data FROM campaigns WHERE id=?",(campaign_id,)).fetchone()
            if row is None: raise StateError("campaign_missing")
            record=Campaign.model_validate({**json.loads(row[0]),**changes})
            self.validate_references(record)
            db.execute("UPDATE campaigns SET data=? WHERE id=?",(_dump(record),campaign_id))
        return record

    def claim_draw(self,campaign_id,draw_id,paid_admitted=True):
        with self._transaction() as db:
            existing=db.execute("SELECT * FROM draws WHERE id=?",(draw_id,)).fetchone()
            if existing:
                if existing["campaign_id"]!=campaign_id: raise StateError("draw_campaign_mismatch")
                return existing["ordinal"]
            if not paid_admitted: return 0
            row=db.execute("SELECT data FROM campaigns WHERE id=?",(campaign_id,)).fetchone()
            if row is None: raise StateError("campaign_missing")
            campaign=Campaign.model_validate_json(row[0])
            if campaign.draws_started>=campaign.max_draws: raise StateError("draw_quota_exhausted")
            campaign.draws_started+=1
            db.execute("INSERT INTO draws VALUES (?,?,?,?)",(draw_id,campaign_id,campaign.draws_started,utc_now()))
            db.execute("UPDATE campaigns SET data=? WHERE id=?",(_dump(campaign),campaign_id))
            return campaign.draws_started

    def create_run(self,mode,campaign_id=None,card_id=None,card_version=None,budget_account_id=None,config=None,prompt_version="",code_version="",run_id=None,state=None):
        if (card_id is None)!=(card_version is None): raise StateError("card_version_required")
        record=RunRecord(run_id=run_id or stable_id("run"),mode=mode,campaign_id=campaign_id,card_id=card_id,card_version=card_version,budget_account_id=budget_account_id,config=config or {},state=state or {},prompt_version=prompt_version,code_version=code_version)
        if card_id: self.get_card(card_id,card_version)
        with self._transaction() as db:
            db.execute("INSERT INTO runs VALUES (?,?,?)",(record.run_id,campaign_id,_dump(record)))
            if card_id: db.execute("INSERT INTO run_cards VALUES (?,?,?)",(record.run_id,card_id,card_version))
        return record

    def get_run(self,run_id):
        with self._connect() as db:
            row=db.execute("SELECT data FROM runs WHERE id=?",(run_id,)).fetchone()
        if row is None: raise StateError("run_missing")
        return RunRecord.model_validate_json(row[0])

    def update_run(self,run_id,**changes):
        if set(changes)&{"run_id","mode","campaign_id","budget_account_id","config","prompt_version","code_version","created_at"}:
            raise StateError("run_identity_configuration_immutable")
        with self._transaction() as db:
            row=db.execute("SELECT data FROM runs WHERE id=?",(run_id,)).fetchone()
            if row is None: raise StateError("run_missing")
            record=RunRecord.model_validate({**json.loads(row[0]),**changes,"updated_at":utc_now()})
            if (record.card_id is None)!=(record.card_version is None): raise StateError("card_version_required")
            if record.card_id:
                db.execute("INSERT OR IGNORE INTO run_cards VALUES (?,?,?)",(run_id,record.card_id,record.card_version))
            db.execute("UPDATE runs SET data=? WHERE id=?",(_dump(record),run_id))
        return record

    def link_card(self,run_id,card_id,version):
        with self._transaction() as db:
            db.execute("INSERT OR IGNORE INTO run_cards VALUES (?,?,?)",(run_id,card_id,version))

    def save_card(self,draft,card_id=None,parent_version=None,selection=None,assessment=None,creation_key=None,run_id=None,state_patch=None):
        draft=CardDraft.model_validate(draft)
        self.validate_references(draft)
        self._validate_claim_evidence(draft)
        input_hash=hashlib.sha256(_dump({"draft":draft.model_dump(mode="json"),"card_id":card_id,"parent_version":parent_version}).encode()).hexdigest()
        with self._transaction() as db:
            if creation_key:
                created=db.execute("SELECT * FROM card_creation WHERE creation_key=?",(creation_key,)).fetchone()
                if created:
                    if created["input_hash"]!=input_hash: raise StateError("card_creation_input_changed")
                    return self.get_card(created["card_id"],created["version"])
            actual_id=card_id or stable_id("card")
            latest=db.execute("SELECT version,data FROM cards WHERE card_id=? ORDER BY version DESC LIMIT 1",(actual_id,)).fetchone()
            if latest:
                if parent_version!=latest["version"]: raise StateError("card_parent_not_latest")
                prior=ResearchCard.model_validate_json(latest["data"])
                self.validate_claim_dependencies(prior,draft)
                version=latest["version"]+1
            else:
                if parent_version is not None: raise StateError("card_parent_missing")
                version=1
            record=ResearchCard(card_id=actual_id,version=version,draft=draft,parent_version=parent_version,selection=selection,assessment=assessment)
            db.execute("INSERT INTO cards VALUES (?,?,?)",(actual_id,version,_dump(record)))
            if creation_key:
                db.execute("INSERT INTO card_creation VALUES (?,?,?,?)",(creation_key,actual_id,version,input_hash))
            if run_id:
                row=db.execute("SELECT data FROM runs WHERE id=?",(run_id,)).fetchone()
                if row is None: raise StateError("run_missing")
                run=RunRecord.model_validate_json(row[0])
                run.card_id=actual_id; run.card_version=version
                run.state.update(state_patch or {})
                db.execute("UPDATE runs SET data=? WHERE id=?",(_dump(run),run_id))
                db.execute("INSERT OR IGNORE INTO run_cards VALUES (?,?,?)",(run_id,actual_id,version))
            body=" ".join(_tokens(_dump(draft)))
            db.execute("INSERT INTO archive_fts(card_id,version,body) VALUES (?,?,?)",(actual_id,version,body))
        return record

    def get_card(self,card_id,version=None):
        with self._connect() as db:
            if version is None:
                row=db.execute("SELECT data,version FROM cards WHERE card_id=? ORDER BY version DESC LIMIT 1",(card_id,)).fetchone()
            else:
                row=db.execute("SELECT data,version FROM cards WHERE card_id=? AND version=?",(card_id,version)).fetchone()
            if row is None: raise StateError("card_missing")
            card=ResearchCard.model_validate_json(row["data"])
            judgment=db.execute("SELECT data FROM selections WHERE card_id=? AND version=?",(card_id,card.version)).fetchone()
        if judgment:
            accepted=SelectorResult.model_validate_json(judgment[0])
            card.selection_result=accepted
            card.selection=accepted.selection
            card.assessment=accepted.assessment
        return card

    def list_cards(self,run_id=None,campaign_id=None):
        with self._connect() as db:
            if run_id is not None:
                rows=db.execute("SELECT card_id,version FROM run_cards WHERE run_id=? ORDER BY rowid",(run_id,)).fetchall()
            elif campaign_id is not None:
                rows=db.execute("SELECT DISTINCT c.card_id,c.version FROM run_cards c JOIN runs r ON r.id=c.run_id WHERE r.campaign_id=?",(campaign_id,)).fetchall()
            else:
                rows=db.execute("SELECT card_id,max(version) as version FROM cards GROUP BY card_id ORDER BY card_id").fetchall()
        return [self.get_card(r["card_id"],r["version"]) for r in rows]

    def card_provenance_context(self,card_id,version):
        """Read the selected version's research inputs, never inherit judgments."""
        from .schemas import InvestigatorResult
        from pydantic import ValidationError
        card=self.get_card(card_id,version)
        source_ids=set(card.draft.closest_work_delta.source_ids)
        evidence_ids=set(card.draft.motivation.evidence_ids)
        for claim in card.draft.claims: evidence_ids.update(claim.evidence_ids)
        with self._connect() as db:
            rows=db.execute("SELECT r.data FROM runs r JOIN run_cards c ON c.run_id=r.id WHERE c.card_id=? AND c.version=? ORDER BY r.rowid",(card_id,version)).fetchall()
        prior_runs=[RunRecord.model_validate_json(row[0]) for row in rows]
        investigations=[]
        for run in prior_runs:
            source_ids.update(run.state.get("source_ids",[]))
            evidence_ids.update(run.state.get("evidence_ids",[]))
            for task in self.list_tasks(run.run_id):
                if task.status!="ACCEPTED" or not isinstance(task.accepted_result,dict): continue
                if not isinstance(task.prompt_manifest,dict) or "roles/investigator.md" not in task.prompt_manifest: continue
                try:
                    InvestigatorResult.model_validate(task.accepted_result.get("result"))
                except ValidationError:
                    continue
                investigations.append(task.task_id)
        source_ids.update(e.source_id for e in self.list_evidence(ids=sorted(evidence_ids)))
        context={"card_id":card_id,"card_version":version,
            "source_ids":sorted(source_ids),"evidence_ids":sorted(evidence_ids),
            "provenance_run_ids":[run.run_id for run in prior_runs],
            "provenance_campaign_ids":sorted({run.campaign_id for run in prior_runs if run.campaign_id}),
            "investigation_task_ids":sorted(set(investigations))}
        self.validate_references({"source_ids":context["source_ids"],"evidence_ids":context["evidence_ids"]})
        return context

    def record_selection(self,run_id,card_id,version,judgment,state_patch=None):
        result=SelectorResult.model_validate(judgment)
        self.validate_references(result)
        self.get_card(card_id,version)
        with self._transaction() as db:
            old=db.execute("SELECT data FROM selections WHERE card_id=? AND version=?",(card_id,version)).fetchone()
            if old and SelectorResult.model_validate_json(old[0])!=result:
                raise StateError("selection_already_accepted")
            db.execute("INSERT OR IGNORE INTO selections VALUES (?,?,?,?)",(card_id,version,run_id,_dump(result)))
            if run_id: db.execute("INSERT OR IGNORE INTO run_cards VALUES (?,?,?)",(run_id,card_id,version))
            if run_id and state_patch and not old:
                row=db.execute("SELECT data FROM runs WHERE id=?",(run_id,)).fetchone()
                if row is None: raise StateError("run_missing")
                run=RunRecord.model_validate_json(row[0]); run.state.update(state_patch)
                run.updated_at=utc_now()
                db.execute("UPDATE runs SET data=? WHERE id=?",(_dump(run),run_id))
        return self.get_card(card_id,version)

    def save_selection(self,card_id,version,judgment):
        return self.record_selection(None,card_id,version,judgment)

    def register_source(self,source,content=None):
        source=SourceRecord.model_validate(source)
        if not source.arxiv_id and source.url:
            arxiv_url=re.search(r"arxiv\.org/(?:abs|pdf|html)/([^?#]+)",source.url)
            if arxiv_url: source.arxiv_id=arxiv_url[1].removesuffix(".pdf")
        canonical=canonical_source(source)
        # DOI/arXiv may identify a source even if its supplied URL is malformed.
        if source.url:
            parsed=urlsplit(source.url)
            if parsed.scheme not in {"http","https"} or not parsed.hostname or parsed.username or parsed.password:
                raise StateError("invalid_source_url")
        version=source.version or ""
        if source.arxiv_id:
            found=re.search(r"v(\d+)$",source.arxiv_id)
            if found:
                if version and version not in {found[1],"v"+found[1],source.arxiv_id}:
                    raise StateError("source_version_identifier_mismatch")
                version=found[1]
        source.version=version or None
        if source.content_origin=="original" and source.source_type=="secondary_analysis":
            raise StateError("secondary_analysis_cannot_be_original")
        if source.origin_source_id: self.get_source(source.origin_source_id)
        source.canonical_id=canonical
        if content is not None:
            digest=hashlib.sha256(content.encode("utf-8")).hexdigest()
            source.content_sha256=digest
            source.content_path=self.save_artifact(f"sources/{source.source_id}/{digest}.txt",content)
            source.access_status="retrieved"
        elif source.access_status=="retrieved" and not source.content_path:
            raise StateError("retrieved_source_requires_content")
        if source.content_path:
            raw=self.read_artifact(source.content_path)
            if source.content_sha256 and hashlib.sha256(raw.encode("utf-8")).hexdigest()!=source.content_sha256:
                raise StateError("source_artifact_hash_mismatch")
            if source.content_total_chars is not None:
                if len(raw)>source.content_total_chars or (source.content_complete and len(raw)!=source.content_total_chars):
                    raise StateError("source_content_completeness_mismatch")
        with self._transaction() as db:
            old=db.execute("SELECT data FROM sources WHERE canonical_id=? AND version=? AND origin=? AND COALESCE(json_extract(data,'$.representation_id'),'')=?",(canonical,version,source.content_origin,source.representation_id or "")).fetchone()
            if old:
                previous=SourceRecord.model_validate_json(old[0])
                if previous.content_sha256 and source.content_sha256 and previous.content_sha256!=source.content_sha256:
                    previous_text=self.read_artifact(previous.content_path)
                    total_agrees=previous.content_total_chars is None or source.content_total_chars==previous.content_total_chars
                    if (previous.representation_id and source.representation_id==previous.representation_id
                            and total_agrees and not source.content_complete
                            and previous_text.startswith(raw)):
                        return previous
                    if (previous.content_complete or not previous.representation_id
                            or source.representation_id!=previous.representation_id or not total_agrees
                            or not raw.startswith(previous_text) or len(raw)<=len(previous_text)):
                        raise StateError("source_changed_requires_explicit_version")
                    # Same declared representation, now with a longer original
                    # prefix. Existing chars/lines locators keep their meaning;
                    # immutable earlier artifacts remain available in the trace.
                    source.source_id=previous.source_id
                    db.execute("UPDATE sources SET data=? WHERE id=?",(_dump(source),source.source_id))
                    return source
                if not previous.content_path and source.content_path:
                    source.source_id=previous.source_id
                    db.execute("UPDATE sources SET data=? WHERE id=?",(_dump(source),source.source_id))
                    return source
                return previous
            db.execute("INSERT INTO sources VALUES (?,?,?,?,?)",(source.source_id,canonical,version,source.content_origin,_dump(source)))
        return source

    def get_source(self,source_id):
        with self._connect() as db:
            row=db.execute("SELECT data FROM sources WHERE id=?",(source_id,)).fetchone()
        if row is None: raise StateError("unknown_source_id")
        return SourceRecord.model_validate_json(row[0])

    def list_sources(self,ids=None):
        return self._list_records("sources",SourceRecord,ids)

    def list_evidence(self,ids=None,run_id=None):
        if run_id is not None:
            with self._connect() as db:
                rows=db.execute("SELECT data FROM evidence WHERE run_id=? ORDER BY rowid",(run_id,)).fetchall()
            records=[EvidenceRecord.model_validate_json(r[0]) for r in rows]
            return records if ids is None else [r for r in records if r.evidence_id in ids]
        return self._list_records("evidence",EvidenceRecord,ids)

    def _list_records(self,table,model,ids=None):
        if ids==[]: return []
        with self._connect() as db:
            if ids is None: rows=db.execute(f"SELECT data FROM {table} ORDER BY rowid").fetchall()
            else:
                rows=db.execute(f"SELECT data FROM {table} WHERE id IN ({','.join('?' for _ in ids)}) ORDER BY rowid",tuple(ids)).fetchall()
        return [model.model_validate_json(row[0]) for row in rows]

    def validate_evidence(self,evidence):
        evidence=EvidenceRecord.model_validate(evidence)
        source=self.get_source(evidence.source_id)
        if source.content_origin=="secondary_analysis" and evidence.origin=="original":
            raise StateError("secondary_evidence_mislabeled_original")
        content=self.read_artifact(source.content_path) if source.content_path else None
        if evidence.excerpt:
            normalized=lambda value:" ".join(value.split())
            if content is None or normalized(evidence.excerpt) not in normalized(content):
                raise StateError("excerpt_not_in_returned_source")
        if evidence.locator_status=="verified" and (not content or not evidence.locator):
            raise StateError("verified_locator_requires_source")
        if evidence.locator_status=="verified":
            line_locator=re.fullmatch(r"(?:[Ll]ines?\s+|L)(\d+)(?:[-–:](?:L)?(\d+))?",evidence.locator.strip())
            char_locator=re.fullmatch(r"chars:(\d+):(\d+)",evidence.locator.strip())
            if line_locator:
                start=int(line_locator[1]); end=int(line_locator[2] or start)
                if start<1 or end<start or end>len(content.splitlines()):
                    raise StateError("locator_not_in_returned_source")
                if evidence.excerpt and " ".join(evidence.excerpt.split()) not in " ".join("\n".join(content.splitlines()[start-1:end]).split()):
                    raise StateError("excerpt_not_at_locator")
            elif char_locator:
                start,end=int(char_locator[1]),int(char_locator[2])
                if start<0 or end<=start or end>len(content):
                    raise StateError("locator_not_in_returned_source")
                if evidence.excerpt and evidence.excerpt!=content[start:end]:
                    raise StateError("excerpt_not_at_locator")
            else:
                raise StateError("verified_locator_requires_checkable_range")
        if evidence.verification_status=="verified":
            if source.content_origin!="original" or not content or not evidence.excerpt or evidence.locator_status!="verified" or not evidence.support_explanation:
                raise StateError("verified_evidence_requires_original_passage_and_explanation")
        if source.access_status=="source_unavailable" and evidence.locator_status!="source_unavailable":
            raise StateError("unavailable_source_locator_mismatch")
        return evidence

    def register_evidence(self,evidence):
        evidence=self.validate_evidence(evidence)
        with self._transaction() as db:
            old=db.execute("SELECT data FROM evidence WHERE id=?",(evidence.evidence_id,)).fetchone()
            if old and EvidenceRecord.model_validate_json(old[0])!=evidence: raise StateError("evidence_immutable")
            db.execute("INSERT OR IGNORE INTO evidence VALUES (?,?,?,?)",(evidence.evidence_id,evidence.source_id,evidence.run_id,_dump(evidence)))
        return evidence

    def validate_finding_sources(self,findings):
        """Pure provenance/quotation checks; no task state or records are written."""
        outputs=[]
        for index,item in enumerate(findings):
            finding=Finding.model_validate(item)
            source=self.get_source(finding.source_id)
            # Persist positions derived from the actual returned bytes decoded as
            # text, never a model's section/page assertion. Repeated excerpts have
            # no unique position unless additional context is supplied.
            content=self.read_artifact(source.content_path) if source.content_path else None
            locator=None
            locator_status="source_unavailable" if source.access_status=="source_unavailable" else "locator_unverified"
            if content and finding.excerpt:
                start=content.find(finding.excerpt)
                if start>=0 and content.find(finding.excerpt,start+1)<0:
                    locator=f"chars:{start}:{start+len(finding.excerpt)}"
                    locator_status="verified"
            record=EvidenceRecord(source_id=source.source_id,
                claim_id=finding.claim_id or "claim_"+hashlib.sha256(_dump({"claim":finding.claim,"conditions":finding.conditions}).encode()).hexdigest()[:24],claim_version=finding.claim_version or 1,
                claim=finding.claim,conditions=finding.conditions,locator=locator,excerpt=finding.excerpt,
                relation=finding.relation,origin=finding.origin,locator_status=locator_status,
                verification_status="verified" if source.content_origin=="original" and finding.origin=="original" and locator_status=="verified" and finding.excerpt and finding.support_explanation else "unverified",
                support_explanation=finding.support_explanation)
            try:
                outputs.append(self.validate_evidence(record))
            except StateError as exc:
                exc.add_note(f"finding[{index}] source_id={finding.source_id}")
                raise
        return outputs

    def validate_findings(self,findings,task_id,*,allowed_claims=None):
        findings=[Finding.model_validate(item) for item in findings]
        records=self.validate_finding_sources(findings)
        task=self.get_task(task_id)
        if task is None: raise StateError("finding_task_missing")
        run=self.get_run(task.run_id)
        from .schemas import Claim
        if allowed_claims is None:
            allowed_claims=self.get_card(run.card_id,run.card_version).draft.claims if run.card_id else []
        allowed={}
        for item in allowed_claims:
            claim=Claim.model_validate(item)
            key=(claim.claim_id,claim.version)
            fingerprint=claim_fingerprint(claim)
            if key in allowed and allowed[key]!=fingerprint:
                raise StateError("finding_ambiguous_target_claim")
            allowed[key]=fingerprint
        registered_claims={(c.claim_id,c.version,claim_fingerprint(c)) for card in self.list_cards(run_id=task.run_id) for c in card.draft.claims}
        if not {(key[0],key[1],fingerprint) for key,fingerprint in allowed.items()}<=registered_claims:
            raise StateError("finding_allowed_claim_not_registered_for_run")
        outputs=[]
        for index,(finding,record) in enumerate(zip(findings,records)):
            if finding.claim_id is not None and (finding.claim_id,finding.claim_version) not in allowed:
                raise StateError("finding_target_claim_not_in_current_input")
            eid="ev_"+hashlib.sha256(f"{task_id}:{index}:{_dump(finding)}".encode()).hexdigest()[:32]
            existing=self.list_evidence(ids=[eid])
            outputs.extend(existing or [record.model_copy(update={"evidence_id":eid,"run_id":task.run_id,
                "target_claim_fingerprint":allowed.get((finding.claim_id,finding.claim_version)) if finding.claim_id is not None else None})])
        return outputs

    def register_findings(self,findings,task_id,*,allowed_claims=None):
        records=self.validate_findings(findings,task_id,allowed_claims=allowed_claims)
        with self._transaction() as db:
            for record in records:
                old=db.execute("SELECT data FROM evidence WHERE id=?",(record.evidence_id,)).fetchone()
                if old and EvidenceRecord.model_validate_json(old[0])!=record:
                    raise StateError("evidence_immutable")
                db.execute("INSERT OR IGNORE INTO evidence VALUES (?,?,?,?)",(record.evidence_id,record.source_id,record.run_id,_dump(record)))
        return records

    def put_task(self,task):
        task=TaskRecord.model_validate(task)
        if task.response_artifact_path: self.read_artifact(task.response_artifact_path)
        if task.rendered_prompt_path: self.read_artifact(task.rendered_prompt_path)
        if (task.environment_snapshot_path is None)!=(task.environment_snapshot_hash is None):
            raise StateError("environment_snapshot_requires_path_and_hash")
        if task.environment_snapshot_path:
            environment=self.read_artifact(task.environment_snapshot_path)
            if hashlib.sha256(environment.encode("utf-8")).hexdigest()!=task.environment_snapshot_hash:
                raise StateError("environment_snapshot_hash_mismatch")
        if task.status in {"RESPONSE_SAVED","ACCEPTED"} and not task.response_artifact_path:
            raise StateError("response_state_requires_artifact")
        if task.status=="ACCEPTED" and task.accepted_result is None:
            raise StateError("accepted_task_requires_result")
        with self._transaction() as db:
            row=db.execute("SELECT data FROM tasks WHERE id=?",(task.task_id,)).fetchone()
            if row:
                previous=TaskRecord.model_validate_json(row[0])
                for field in ("run_id","input_hash","prompt_hash","model_config_hash",
                              "environment_snapshot_path","environment_snapshot_hash","evidence_ids"):
                    if getattr(previous,field)!=getattr(task,field): raise StateError("task_dependency_changed_requires_fork")
                if previous.status=="ACCEPTED" and (task.status!="ACCEPTED" or previous.accepted_result!=task.accepted_result):
                    raise StateError("accepted_task_immutable")
                if not set(previous.attempt_ids)<=set(task.attempt_ids): raise StateError("attempt_history_lost")
            task.updated_at=utc_now()
            db.execute("INSERT INTO tasks VALUES (?,?,?) ON CONFLICT(id) DO UPDATE SET data=excluded.data",(task.task_id,task.run_id,_dump(task)))
        return task

    def get_task(self,task_id):
        with self._connect() as db:
            row=db.execute("SELECT data FROM tasks WHERE id=?",(task_id,)).fetchone()
        return TaskRecord.model_validate_json(row[0]) if row else None

    def list_tasks(self,run_id):
        with self._connect() as db:
            rows=db.execute("SELECT data FROM tasks WHERE run_id=? ORDER BY rowid",(run_id,)).fetchall()
        return [TaskRecord.model_validate_json(row[0]) for row in rows]

    def get_issues(self,run_id):
        with self._connect() as db:
            rows=db.execute("SELECT data FROM issues WHERE run_id=? ORDER BY rowid",(run_id,)).fetchall()
        return [Issue.model_validate_json(row[0]) for row in rows]

    def apply_issues(self,run_id,updated_issues,transitions,event_key=None,state_patch=None):
        incoming=[Issue.model_validate(i) for i in updated_issues]
        changes=[IssueTransition.model_validate(t) for t in transitions]
        ids=[i.issue_id for i in incoming]
        tids=[t.issue_id for t in changes]
        if len(ids)!=len(set(ids)) or len(tids)!=len(set(tids)) or set(ids)!=set(tids):
            raise StateError("issue_transition_set_mismatch")
        self.validate_references(incoming)
        self.validate_references(changes)
        event_hash=hashlib.sha256(_dump({"issues":incoming,"transitions":changes,"state_patch":state_patch}).encode()).hexdigest()
        with self._transaction() as db:
            if event_key:
                applied=db.execute("SELECT * FROM issue_applied WHERE event_key=?",(event_key,)).fetchone()
                if applied:
                    if applied["run_id"]!=run_id or applied["input_hash"]!=event_hash: raise StateError("issue_event_reused_with_different_state")
                    return self.get_issues(run_id)
            run_row=db.execute("SELECT data FROM runs WHERE id=?",(run_id,)).fetchone()
            if run_row is None: raise StateError("run_missing")
            run=RunRecord.model_validate_json(run_row[0])
            known_claims={(e.claim_id,e.claim_version) for e in self.list_evidence()}
            card_claims={}
            if run.card_id:
                card_claims={(c.claim_id,c.version):c for c in self.get_card(run.card_id,run.card_version).draft.claims}
                known_claims.update(card_claims)
            old={row["id"]:Issue.model_validate_json(row["data"]) for row in db.execute("SELECT * FROM issues WHERE run_id=?",(run_id,))}
            if not set(old)<=set(ids): raise StateError("previous_issue_silently_dropped")
            by_id={i.issue_id:i for i in incoming}
            for transition in changes:
                previous=old.get(transition.issue_id)
                issue=by_id[transition.issue_id]
                if previous is None and (issue.claim_id,issue.claim_version) not in known_claims:
                    raise StateError("issue_refers_to_unknown_claim_version")
                if transition.from_status!=(previous.status if previous else None) or transition.to_status!=issue.status:
                    raise StateError("issue_transition_status_mismatch")
                if previous and (previous.claim_id!=issue.claim_id or previous.claim_version!=issue.claim_version):
                    raise StateError("issue_claim_identity_changed")
                if previous and previous.claim_kind!=issue.claim_kind:
                    raise StateError("issue_claim_kind_changed")
                canonical_claim=card_claims.get((issue.claim_id,issue.claim_version))
                if canonical_claim and canonical_claim.kind!=issue.claim_kind:
                    raise StateError("issue_claim_kind_mismatch")
                if previous and previous.status in {"resolved","withdrawn"} and issue.status not in {"resolved","withdrawn"}:
                    if not transition.new_evidence_or_argument: raise StateError("reopen_requires_new_basis")
                if issue.status=="resolved" and (previous is None or previous.status!="resolved"):
                    if issue.claim_kind=="empirical" and not transition.basis_evidence_ids:
                        raise StateError("empirical_issue_not_resolved_by_agreement")
                    if issue.claim_kind=="empirical":
                        resolution_claim=canonical_claim
                        if run.card_id and resolution_claim is None:
                            resolution_claim=next((claim for card in self.list_cards(run_id=run_id)
                                if card.card_id==run.card_id for claim in card.draft.claims
                                if (claim.claim_id,claim.version)==(issue.claim_id,issue.claim_version)),None)
                        if run.card_id and resolution_claim is None:
                            raise StateError("empirical_resolution_requires_verified_claim_evidence")
                        basis=self.list_evidence(ids=transition.basis_evidence_ids)
                        if not any(e.verification_status=="verified" and e.claim_id==issue.claim_id and e.claim_version==issue.claim_version and e.relation in {"supports","challenges"}
                            and (run.card_id is None or e.target_claim_fingerprint==claim_fingerprint(resolution_claim)) for e in basis):
                            raise StateError("empirical_resolution_requires_verified_claim_evidence")
                    if not (transition.basis_evidence_ids or transition.basis_argument):
                        raise StateError("resolution_requires_basis")
                if issue.redirect_to and issue.redirect_to not in by_id: raise StateError("unknown_issue_redirect")
                db.execute("INSERT INTO issues VALUES (?,?,?) ON CONFLICT(run_id,id) DO UPDATE SET data=excluded.data",(run_id,issue.issue_id,_dump(issue)))
            db.execute("INSERT INTO issue_events(run_id,data,created_at) VALUES (?,?,?)",(run_id,_dump(changes),utc_now()))
            if event_key:
                db.execute("INSERT INTO issue_applied VALUES (?,?,?)",(event_key,run_id,event_hash))
            if state_patch:
                run.state.update(state_patch)
                run.updated_at=utc_now()
                db.execute("UPDATE runs SET data=? WHERE id=?",(_dump(run),run_id))
        return incoming

    def validate_claim_dependencies(self,original,draft):
        draft=CardDraft.model_validate(draft)
        if original.draft.problem_anchor!=draft.problem_anchor: raise StateError("problem_anchor_changed")
        self.validate_references(draft)
        old={c.claim_id:c for c in original.draft.claims}
        for claim in draft.claims:
            previous=old.get(claim.claim_id)
            if previous and claim.version<previous.version: raise StateError("claim_version_cannot_regress")
            changed=previous and (previous.text!=claim.text or previous.conditions!=claim.conditions or previous.kind!=claim.kind)
            if changed and claim.version<=previous.version: raise StateError("changed_claim_requires_new_version")
        self._validate_claim_evidence(draft)

    def _validate_claim_evidence(self,draft):
        for claim in draft.claims:
            for evidence in self.list_evidence(ids=claim.evidence_ids):
                if evidence.claim_id==claim.claim_id and evidence.claim_version!=claim.version:
                    raise StateError("claim_evidence_version_mismatch")

    def claim_evidence_bindings(self,draft):
        """Describe reference targets without transferring scientific validation."""
        draft=CardDraft.model_validate(draft)
        self.validate_references(draft)
        self._validate_claim_evidence(draft)
        bindings=[]
        for claim in draft.claims:
            for evidence in self.list_evidence(ids=claim.evidence_ids):
                bindings.append({"claim_id":claim.claim_id,"claim_version":claim.version,
                    "evidence_id":evidence.evidence_id,"evidence_claim_id":evidence.claim_id,
                    "evidence_claim_version":evidence.claim_version,"source_id":evidence.source_id,
                    "binding":"current_claim_target" if evidence.claim_id==claim.claim_id and evidence.claim_version==claim.version
                        and evidence.target_claim_fingerprint==claim_fingerprint(claim) else "background_premise",
                    "relation":evidence.relation,"evidence_verification_status":evidence.verification_status,
                    "verification_transferred":False})
        return bindings

    def validate_references(self,obj):
        value=obj.model_dump(mode="json") if isinstance(obj,BaseModel) else obj
        if isinstance(value,list):
            for item in value: self.validate_references(item)
            return
        if not isinstance(value,dict): return
        for key,item in value.items():
            if item is None: continue
            if key in {"source_id","source_ids","target_source_ids","original_sources_revisited"}:
                refs=item if isinstance(item,list) else [item]
                if len(refs)!=len(set(refs)): raise StateError("duplicate_source_reference")
                for ref in refs: self.get_source(ref)
            elif key in {"evidence_id","evidence_ids","anchor_evidence_ids","trigger_evidence_ids","decisive_evidence_ids","basis_evidence_ids","new_evidence_ids"}:
                refs=item if isinstance(item,list) else [item]
                if len(refs)!=len(set(refs)): raise StateError("duplicate_evidence_reference")
                if len(self.list_evidence(ids=refs))!=len(refs): raise StateError("unknown_evidence_id")
            elif isinstance(item,(dict,list)): self.validate_references(item)

    def save_direction_change(self,run_id,change,original_audit=None):
        change=DirectionChangeDraft.model_validate(change)
        self.validate_references(change)
        run=self.get_run(run_id)
        if not run.card_id: raise StateError("scope_change_card_required")
        card=self.get_card(run.card_id,run.card_version)
        if card.draft.problem_anchor==change.proposed_problem_anchor: raise StateError("scope_change_requires_new_anchor")
        inherited_sources=set(card.draft.closest_work_delta.source_ids)
        evidence_ids=list(card.draft.motivation.evidence_ids)+[eid for claim in card.draft.claims for eid in claim.evidence_ids]
        inherited_sources.update(e.source_id for e in self.list_evidence(ids=evidence_ids))
        if not set(change.original_sources_revisited)<=inherited_sources:
            raise StateError("scope_audit_did_not_revisit_inherited_sources")
        for source_id in change.original_sources_revisited:
            source=self.get_source(source_id)
            if source.content_origin!="original" or source.access_status!="retrieved" or not source.content_path:
                raise StateError("scope_audit_requires_returned_original_sources")
        if not original_audit: raise StateError("scope_change_requires_original_audit")
        event=DirectionChange(**change.model_dump(),run_id=run_id,parent_card_id=run.card_id,parent_card_version=run.card_version)
        with self._transaction() as db:
            old=db.execute("SELECT data FROM direction_changes WHERE run_id=?",(run_id,)).fetchone()
            if old:
                existing=DirectionChange.model_validate_json(old[0])
                if any(getattr(existing,field)!=getattr(change,field) for field in DirectionChangeDraft.model_fields):
                    raise StateError("only_one_frozen_direction")
                return existing
            db.execute("INSERT INTO direction_changes VALUES (?,?,?,?)",(event.direction_change_id,run_id,_dump(event),_dump(original_audit)))
            run.status="PAUSED_SCOPE_CHANGE"
            run.assessment="SCOPE_CHANGE_PROPOSED"
            run.stop_reason="scope_change_requires_user"
            db.execute("UPDATE runs SET data=? WHERE id=?",(_dump(run),run_id))
        return event

    def list_direction_changes(self,run_id):
        with self._connect() as db:
            rows=db.execute("SELECT data FROM direction_changes WHERE run_id=?",(run_id,)).fetchall()
        return [DirectionChange.model_validate_json(r[0]) for r in rows]

    get_scope_changes=list_direction_changes

    def list_capability_requests(self,run_id):
        with self._connect() as db:
            rows=db.execute("SELECT id,run_id,data FROM capabilities WHERE run_id=? ORDER BY rowid",(run_id,)).fetchall()
        return [{"request_id":r["id"],"run_id":r["run_id"],**json.loads(r["data"])} for r in rows]

    def get_capability_request(self,request_id):
        with self._connect() as db:
            row=db.execute("SELECT id,run_id,data FROM capabilities WHERE id=?",(request_id,)).fetchone()
        if row is None: raise StateError("record_missing")
        return {"request_id":row["id"],"run_id":row["run_id"],**json.loads(row["data"])}

    def save_capability_request(self,run_id,request,*,task_id=None,request_key=None):
        from .schemas import CapabilityRequest
        record=CapabilityRequest.model_validate(request)
        identifier=f"cap_{run_id}.{request_key}" if request_key is not None else stable_id("cap")
        data={**record.model_dump(mode="json"),"status":"pending_codex_review",
              "created_at":utc_now(),"review":None,"reviewed_at":None,"task_id":task_id}
        with self._transaction() as db:
            existing=db.execute("SELECT run_id,data FROM capabilities WHERE id=?",(identifier,)).fetchone()
            if existing is not None:
                previous=json.loads(existing["data"])
                if existing["run_id"]!=run_id or previous["task_id"]!=task_id or any(previous[k]!=v for k,v in record.model_dump(mode="json").items()):
                    raise StateError("capability_request_key_conflict")
                return identifier
            db.execute("INSERT INTO capabilities VALUES (?,?,?)",(identifier,run_id,_dump(data)))
        return identifier

    def review_capability_request(self,request_id,review):
        """Record an explicit CodeX assessment; this grants no execution authority."""
        from .schemas import CapabilityReview
        review=CapabilityReview.model_validate(review).model_dump(mode="json")
        with self._transaction() as db:
            row=db.execute("SELECT data FROM capabilities WHERE id=?",(request_id,)).fetchone()
            if row is None: raise StateError("record_missing")
            data=json.loads(row["data"])
            if data["review"] is not None:
                if data["review"] != review: raise StateError("capability_review_already_recorded")
            else:
                data.update(status="reviewed",review=review,reviewed_at=utc_now())
                db.execute("UPDATE capabilities SET data=? WHERE id=?",(_dump(data),request_id))
        return self.get_capability_request(request_id)

    def lookup_archive(self,query,limit=8,offset=0):
        if not 1<=limit<=100 or offset<0: raise ValueError("invalid_archive_window")
        tokens=_tokens(query)
        with self._connect() as db:
            exact=db.execute("SELECT card_id,version FROM cards WHERE card_id=? ORDER BY version DESC",(query,)).fetchall()
            identifier=query.strip().casefold()
            if identifier.startswith("https://doi.org/"): identifier="doi:"+identifier.removeprefix("https://doi.org/")
            elif re.match(r"^10\.\d{4,9}/",identifier): identifier="doi:"+identifier
            elif re.fullmatch(r"(?:arxiv:)?\d{4}\.\d{4,5}(?:v\d+)?",identifier): identifier="arxiv:"+re.sub(r"v\d+$","",identifier.removeprefix("arxiv:"))
            source_rows=db.execute("SELECT id FROM sources WHERE id=? OR lower(canonical_id)=?",(query,identifier)).fetchall()
            if not exact and source_rows:
                source_ids=[r[0] for r in source_rows]
                slots=','.join('?' for _ in source_ids)
                exact=db.execute(f"""SELECT DISTINCT c.card_id,c.version FROM cards c WHERE
                  EXISTS(SELECT 1 FROM json_each(c.data,'$.draft.closest_work_delta.source_ids') j WHERE j.value IN ({slots}))
                  OR EXISTS(SELECT 1 FROM json_each(c.data,'$.draft.motivation.evidence_ids') j JOIN evidence e ON e.id=j.value WHERE e.source_id IN ({slots}))
                  ORDER BY c.card_id,c.version DESC""",tuple(source_ids+source_ids)).fetchall()
            if exact:
                rows=exact[offset:offset+limit]; total=len(exact)
            elif tokens:
                match=" OR ".join('"'+token.replace('"','""')+'"' for token in tokens)
                total=db.execute("SELECT count(*) FROM archive_fts WHERE archive_fts MATCH ?",(match,)).fetchone()[0]
                rows=db.execute("SELECT card_id,version FROM archive_fts WHERE archive_fts MATCH ? ORDER BY bm25(archive_fts),card_id,version LIMIT ? OFFSET ?",(match,limit,offset)).fetchall()
            else: rows=[]; total=0
        records=[]
        for row in rows:
            card=self.get_card(row["card_id"],int(row["version"]))
            records.append({"card_id":card.card_id,"version":card.version,"title":card.draft.title,
                "problem_anchor":card.draft.problem_anchor.model_dump(),"knowledge_increment":card.draft.contribution.knowledge_increment,
                "selection":card.selection,"reopen_conditions":card.draft.risks.reopen_conditions})
        return {"records":records,"total":total,"offset":offset,"limit":limit,
                "unsearched_limits":["lexical_recall_is_not_semantic_uniqueness"]+(["additional_matching_records_require_pagination"] if offset+len(records)<total else [])}

    def get_record(self,id,version=None,run_id=None):
        with self._connect() as db:
            kind=next((table for table in ("sources","evidence","tasks","capabilities","campaigns","runs") if db.execute(f"SELECT 1 FROM {table} WHERE id=?",(id,)).fetchone()),None)
            if kind=="capabilities":
                row=db.execute("SELECT * FROM capabilities WHERE id=?",(id,)).fetchone()
                return {"request_id":row["id"],"run_id":row["run_id"],**json.loads(row["data"])}
            if kind is None:
                if run_id is not None:
                    issues=db.execute("SELECT run_id,data FROM issues WHERE id=? AND run_id=?",(id,run_id)).fetchall()
                else:
                    issues=db.execute("SELECT run_id,data FROM issues WHERE id=?",(id,)).fetchall()
                if len(issues)>1: raise StateError("record_ambiguous_requires_run_id")
                if issues: return {"run_id":issues[0]["run_id"],**Issue.model_validate_json(issues[0]["data"]).model_dump(mode="json")}
                if version is None:
                    card=db.execute("SELECT 1 FROM cards WHERE card_id=?",(id,)).fetchone()
                else:
                    card=db.execute("SELECT 1 FROM cards WHERE card_id=? AND version=?",(id,version)).fetchone()
                if not card: raise StateError("record_missing")
        if kind=="campaigns": return self.get_campaign(id).model_dump(mode="json")
        if kind=="runs":
            run=self.get_run(id)
            evidence_ids=set(run.state.get("evidence_ids",[]))
            source_ids=set(run.state.get("source_ids",[]))
            if run.card_id:
                card=self.get_card(run.card_id,run.card_version)
                source_ids.update(card.draft.closest_work_delta.source_ids)
                evidence_ids.update(card.draft.motivation.evidence_ids)
                for claim in card.draft.claims: evidence_ids.update(claim.evidence_ids)
            source_ids.update(e.source_id for e in self.list_evidence(ids=sorted(evidence_ids)))
            return {"run_id":run.run_id,"campaign_id":run.campaign_id,"mode":run.mode,
                    "card_id":run.card_id,"card_version":run.card_version,
                    "status":run.status,"assessment":run.assessment,"stop_reason":run.stop_reason,
                    "budget_account_id":run.budget_account_id,
                    "source_ids":sorted(source_ids),"evidence_ids":sorted(evidence_ids),
                    "issues":[issue.model_dump(mode="json") for issue in self.get_issues(id)]}
        if kind=="sources":
            source=self.get_source(id)
            result=source.model_dump(mode="json")
            result["content"]=self.read_artifact(source.content_path) if source.content_path else None
            return result
        if kind=="evidence": return self.list_evidence(ids=[id])[0].model_dump(mode="json")
        if kind=="tasks":
            task=self.get_task(id)
            return {"task_id":task.task_id,"run_id":task.run_id,"status":task.status,
                    "accepted_result":task.accepted_result,"evidence_ids":task.evidence_ids}
        return self.get_card(id,version).model_dump(mode="json")
