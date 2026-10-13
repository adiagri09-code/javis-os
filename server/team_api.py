"""Route của nhóm chat team (T1) cho dashboard. Spec: docs/superpowers/specs/2026-10-13-team-chat-design.md mục 15.1.

Dashboard có một tài khoản đăng nhập duy nhất; middleware auth và CSRF của main.py chặn trước khi tới đây, nên request
tới được route này là của chủ nhóm (owner). Mọi route kiểm nhóm thuộc đúng brain đang mở: id nhóm của brain khác coi
như không có (404).

Gửi tin đi bằng `POST /teams/{id}/messages` (phán quyết R2 của kế hoạch T1); câu trả lời, trạng thái hàng đợi đẩy về
qua WebSocket chung bằng gói `team_message` / `team_state`. Lượt trả lời và bộ điều phối chạy NỀN (`deps.spawn`), route
trả ngay.

Kho `team.sqlite3` mở lười: chưa ai dùng nhóm thì không có file, vòng điều phối và phục hồi sau restart thoát ngay.
"""
from __future__ import annotations

import asyncio
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Optional

from fastapi import Request
from fastapi.responses import JSONResponse

import localefmt
import resonance_store as RS
import task_store
import team_store
from team_runner import TeamRunner
from team_store import TeamError

LOOP_EVERY_S = 5.0          # nhịp điều phối (spec 8.3: cùng nhịp 5 giây của Kanban)
REMIND_EVERY_S = 3600.0     # nhịp nhắc việc bị chặn quá 24 giờ


@dataclass
class TeamApiDeps:
    brain_key: Callable[[str], str]                    # tên brain trên dashboard -> đường dẫn đã resolve
    session_store: Callable[[], Any]                   # () -> SessionStore
    task_store: Callable[[], Any]                      # () -> TaskStore của Kanban (kanban.sqlite3)
    resonance_store: Callable[[], Any]                 # () -> GoalStore (sổ danh tính agent)
    agents_meta: Callable[[str], list]                 # root -> [{slug, name, ...}]
    agent_info: Callable[[str, str], Optional[dict]]   # (root, agent_key) -> {slug, name, system} | None
    engine_for: Callable[[dict, str, str], tuple]      # (team, agent_key, role) -> (engine, model, async fn)
    broadcast: Optional[Callable[[dict], Any]] = None  # gói WS tới mọi tab (async)
    notify: Optional[Callable[[str, str], Any]] = None  # (session_id nhóm, chữ) -> hộp thư (async)
    spawn: Callable[[Any], Any] = field(default=asyncio.ensure_future)
    store_path: Optional[Path] = None                  # mặc định STATE_DIR/team.sqlite3


async def _body(request: Request) -> dict:
    try:
        data = await request.json()
        return data if isinstance(data, dict) else {}
    except Exception:  # noqa: BLE001
        return {}


def _err(code: int, vi: str, en: str, **extra) -> JSONResponse:
    return JSONResponse({"ok": False, "error": localefmt.chu(vi, en), **extra}, status_code=code)


def _team_err(ex: Exception, code: int = 400) -> JSONResponse:
    return JSONResponse({"ok": False, "error": str(ex)}, status_code=code)


class TeamApi:
    def __init__(self, deps: TeamApiDeps):
        self.deps = deps
        self._teams = None
        self._runner = None
        self._loop_task = None

    def path(self) -> Path:
        if self.deps.store_path:
            return Path(self.deps.store_path)
        import config as cfgmod
        return Path(cfgmod.STATE_DIR) / "team.sqlite3"

    def exists(self) -> bool:
        return self._teams is not None or self.path().is_file()

    def teams(self) -> team_store.TeamStore:
        if self._teams is None:
            self._teams = team_store.TeamStore(self.path())
        return self._teams

    def _spawn(self, value: Any) -> None:
        if asyncio.iscoroutine(value):
            try:
                self.deps.spawn(value)
            except Exception as ex:  # noqa: BLE001
                value.close()
                print(f"[team] không tạo được việc nền: {type(ex).__name__}: {ex}", file=sys.stderr)

    def runner(self) -> TeamRunner:
        if self._runner is None:
            def publish(ev: dict) -> None:
                if self.deps.broadcast is not None:
                    self._spawn(self.deps.broadcast(ev))

            def notify(team_id: str, text: str) -> None:
                team = self.teams().get(team_id)
                if self.deps.notify is not None and team:
                    self._spawn(self.deps.notify(team["session_id"], text))

            self._runner = TeamRunner(
                teams=self.teams(), tasks=self.deps.task_store(), sessions=self.deps.session_store(),
                engine_for=lambda team, key, role: self.deps.engine_for(team, key, role),
                agent_info=lambda root, key: self.deps.agent_info(root, key),
                publish=publish, notify=notify, worker_id="team-runner")
        return self._runner

    def kick(self) -> None:
        """Đánh thức bộ điều phối ngay (không đợi nhịp 5 giây)."""
        self._spawn(self.runner().dispatch_once(wait=False))

    # ───────────── khung nhìn ─────────────

    def member_views(self, team: dict) -> list:
        root = team["brain_id"]
        names = {m["slug"]: m.get("name") or m["slug"] for m in (self.deps.agents_meta(root) or [])}
        rs = self.deps.resonance_store()
        out = []
        for m in self.teams().members(team["team_id"]):
            reg = rs.agent_by_key(root, m["agent_key"]) or {}
            slug = reg.get("slug") or m["slug_at_join"]
            out.append({"agent_key": m["agent_key"], "slug": slug, "name": names.get(slug) or slug,
                        "role": m["role"], "status": m["status"], "agent_status": reg.get("status") or "",
                        "resonance_enabled": bool(reg.get("enabled")), "joined_at": m["joined_at"]})
        return out

    def counts(self, team_id: str) -> dict:
        q = self.deps.task_store().team_queue(team_id)
        return {"running": len(q["running"]), "waiting": len(q["waiting"]), "blocked": len(q["blocked"])}

    def view(self, team: dict) -> dict:
        q = self.deps.task_store().team_queue(team["team_id"])
        return dict(team, members=self.member_views(team),
                    counts={"running": len(q["running"]), "waiting": len(q["waiting"]), "blocked": len(q["blocked"])},
                    running=[{"id": t["id"], "title": t["title"]} for t in q["running"]],
                    busy=self.runner().busy_view(team["team_id"]))

    def register_agent(self, root: str, slug: str) -> dict:
        return self.deps.resonance_store().agent_register(RS.Principal("owner", "owner", root), slug)

    # ───────────── nền ─────────────

    async def loop(self) -> None:
        """Vòng điều phối: phục hồi sau restart một lần, rồi mỗi 5 giây nhận việc đầu hàng; mỗi giờ nhắc việc chặn lâu."""
        recovered = False
        last_remind = 0.0
        while True:
            try:
                if self.exists():
                    r = self.runner()
                    if not recovered:
                        recovered = True
                        rep = await asyncio.to_thread(r.recover)
                        if rep["resumed"]:
                            self._spawn(r.resume_jobs(rep["resumed"]))
                    await r.dispatch_once(wait=False)
                    now = asyncio.get_running_loop().time()
                    if now - last_remind >= REMIND_EVERY_S:
                        last_remind = now
                        r.remind_blocked()
            except asyncio.CancelledError:
                raise
            except Exception as ex:  # noqa: BLE001
                print(f"[team loop] {type(ex).__name__}: {ex}", file=sys.stderr)
            await asyncio.sleep(LOOP_EVERY_S)


def register(app, deps: TeamApiDeps) -> TeamApi:
    """Đăng ký route `/teams/*`. Gọi SAU route cuối của main.py để bảng route cũ giữ nguyên thứ tự."""
    api = TeamApi(deps)

    @app.on_event("startup")
    async def _team_loop_start():
        api._loop_task = asyncio.create_task(api.loop())

    def _root(brain: str) -> Optional[str]:
        root = deps.brain_key(brain or "")
        return root if root and Path(root).is_dir() else None

    def _team(team_id: str, brain: str):
        root = _root(brain)
        if root is None:
            return None, _err(404, "Không tìm thấy brain", "Brain not found")
        if not api.exists():
            return None, _err(404, "Không có nhóm này", "Team not found")
        team = api.teams().get(team_id)
        if not team or team["brain_id"] != root:
            return None, _err(404, "Không có nhóm này", "Team not found")
        return team, None

    def _slugs(root: str) -> set:
        return {m["slug"] for m in (deps.agents_meta(root) or [])}

    @app.get("/teams")
    async def teams_list(brain: str = "brain", before: Optional[float] = None, limit: int = 50):
        root = _root(brain)
        if root is None:
            return _err(404, "Không tìm thấy brain", "Brain not found")
        if not api.exists():
            return {"ok": True, "teams": [], "next": None}

        def _read():
            rows = api.teams().list_teams(root, limit=limit, before=before)
            return [dict(t, counts=api.counts(t["team_id"])) for t in rows]
        rows = await asyncio.to_thread(_read)
        nxt = rows[-1]["updated_at"] if len(rows) >= max(1, min(int(limit), 200)) else None
        return {"ok": True, "teams": rows, "next": nxt}

    @app.post("/teams")
    async def teams_create(request: Request, brain: str = "brain"):
        root = _root(brain)
        if root is None:
            return _err(404, "Không tìm thấy brain", "Brain not found")
        body = await _body(request)
        name = str(body.get("name") or "").strip()
        members = [str(s) for s in (body.get("members") or []) if str(s or "").strip()]
        leader = str(body.get("leader_slug") or "").strip()
        if not name:
            return _err(400, "Thiếu tên nhóm", "Team name is required")
        have = _slugs(root)
        missing = [s for s in members + ([leader] if leader else []) if s not in have]
        if missing:
            return _err(400, f"Không có trợ lý: {', '.join(missing)}", f"No such assistant: {', '.join(missing)}")
        if leader and leader not in members:
            members.append(leader)
        tid = team_store.new_team_id()
        sid = deps.session_store().create_session(brain=brain, channel=f"team:{tid}", title=name[:120])
        teams = api.teams()
        team = teams.create_team(root, name, str(body.get("description") or ""), sid, team_id=tid)
        keys = {}
        for slug in dict.fromkeys(members):
            reg = api.register_agent(root, slug)
            keys[slug] = reg["agent_key"]
            teams.add_member(tid, reg["agent_key"], slug)
        if leader:
            teams.set_leader(tid, keys[leader])
        return {"ok": True, "team": api.view(teams.get(tid))}

    @app.get("/teams/{team_id}")
    async def teams_get(team_id: str, brain: str = "brain"):
        team, err = _team(team_id, brain)
        if err:
            return err
        return {"ok": True, "team": await asyncio.to_thread(api.view, team)}

    @app.patch("/teams/{team_id}")
    async def teams_patch(team_id: str, request: Request, brain: str = "brain"):
        team, err = _team(team_id, brain)
        if err:
            return err
        body = await _body(request)
        fields = {k: body[k] for k in ("name", "description", "status") if k in body}
        if not fields:
            return {"ok": True, "team": api.view(team)}
        try:
            updated = api.teams().update(team_id, **fields)
        except TeamError as ex:
            return _team_err(ex)
        runner = api.runner()
        if fields.get("status") == "archived":
            q = deps.task_store().team_queue(team_id)
            for t in q["waiting"] + q["blocked"]:
                runner.cancel_job(t["id"], "nhóm đã lưu trữ")
        elif fields.get("status") == "active" and team["status"] != "active":
            api._spawn(runner.resume_team(team_id))
            api.kick()
        runner._state(team_id)
        return {"ok": True, "team": api.view(updated)}

    @app.post("/teams/{team_id}/members")
    async def teams_member_add(team_id: str, request: Request, brain: str = "brain"):
        team, err = _team(team_id, brain)
        if err:
            return err
        slug = str((await _body(request)).get("slug") or "").strip()
        if slug not in _slugs(team["brain_id"]):
            return _err(400, f"Không có trợ lý: {slug}", f"No such assistant: {slug}")
        reg = api.register_agent(team["brain_id"], slug)
        api.teams().add_member(team_id, reg["agent_key"], slug)
        api.runner()._state(team_id)
        return {"ok": True, "team": api.view(api.teams().get(team_id))}

    @app.delete("/teams/{team_id}/members/{agent_key}")
    async def teams_member_remove(team_id: str, agent_key: str, brain: str = "brain"):
        team, err = _team(team_id, brain)
        if err:
            return err
        if not api.teams().remove_member(team_id, agent_key):
            return _err(404, "Không phải thành viên đang hoạt động", "Not an active member")
        api.runner()._state(team_id)
        return {"ok": True, "team": api.view(api.teams().get(team_id))}

    @app.post("/teams/{team_id}/leader")
    async def teams_leader(team_id: str, request: Request, brain: str = "brain"):
        team, err = _team(team_id, brain)
        if err:
            return err
        key = (await _body(request)).get("agent_key")
        try:
            updated = api.teams().set_leader(team_id, str(key) if key else None)
        except TeamError as ex:
            return _team_err(ex)
        if updated["leader_key"]:
            api.runner().resume_no_leader(team_id)
            api.kick()
        api.runner()._state(team_id)
        return {"ok": True, "team": api.view(updated)}

    @app.post("/teams/{team_id}/caps")
    async def teams_caps(team_id: str, request: Request, brain: str = "brain"):
        team, err = _team(team_id, brain)
        if err:
            return err
        try:
            updated = api.teams().set_caps(team_id, (await _body(request)).get("caps") or {})
        except TeamError as ex:
            return _team_err(ex)
        return {"ok": True, "team": api.view(updated)}

    @app.get("/teams/{team_id}/queue")
    async def teams_queue(team_id: str, brain: str = "brain"):
        team, err = _team(team_id, brain)
        if err:
            return err
        q = await asyncio.to_thread(deps.task_store().team_queue, team_id)
        return dict(q, ok=True, busy=api.runner().busy_view(team_id))

    def _own_task(team_id: str, task_id: str) -> Optional[dict]:
        t = deps.task_store().get_task(task_id)
        return t if t and t.get("lane") == "team" and t.get("team_id") == team_id else None

    @app.post("/teams/{team_id}/queue/{task_id}/priority")
    async def teams_priority(team_id: str, task_id: str, request: Request, brain: str = "brain"):
        team, err = _team(team_id, brain)
        if err:
            return err
        if not _own_task(team_id, task_id):
            return _err(404, "Không có việc này trong nhóm", "No such job in this team")
        body = await _body(request)
        try:
            q = deps.task_store().team_priority(task_id, bool(body.get("on", True)),
                                                int(body.get("expected_queue_version") or 0))
        except task_store.QueueConflict as ex:
            return JSONResponse({"ok": False, "code": "queue_changed", "queue": ex.queue,
                                 "error": localefmt.chu("Hàng đợi vừa thay đổi", "The queue just changed")},
                                status_code=409)
        except task_store.QueueError:
            return _err(409, "Việc này không còn ở hàng chờ", "This job is no longer waiting")
        api.runner()._state(team_id)
        return {"ok": True, "queue": q}

    @app.get("/teams/{team_id}/tasks/{task_id}")
    async def teams_task(team_id: str, task_id: str, brain: str = "brain"):
        team, err = _team(team_id, brain)
        if err:
            return err
        task = _own_task(team_id, task_id)
        if not task:
            return _err(404, "Không có việc này trong nhóm", "No such job in this team")

        def _read():
            return {"ok": True, "task": task, "steps": api.teams().steps(task_id),
                    "messages": deps.session_store().team_messages_of_task(team["session_id"], task_id)}
        return await asyncio.to_thread(_read)

    @app.post("/teams/{team_id}/tasks/{task_id}/cancel")
    async def teams_task_cancel(team_id: str, task_id: str, brain: str = "brain"):
        team, err = _team(team_id, brain)
        if err:
            return err
        if not _own_task(team_id, task_id):
            return _err(404, "Không có việc này trong nhóm", "No such job in this team")
        prev = api.runner().cancel_job(task_id)
        if prev is None:
            return _err(409, "Việc đã kết thúc", "The job has already ended")
        api.kick()
        return {"ok": True, "previous": prev}

    @app.post("/teams/{team_id}/tasks/{task_id}/amend")
    async def teams_task_amend(team_id: str, task_id: str, request: Request, brain: str = "brain"):
        team, err = _team(team_id, brain)
        if err:
            return err
        if not _own_task(team_id, task_id):
            return _err(404, "Không có việc này trong nhóm", "No such job in this team")
        text = str((await _body(request)).get("text") or "").strip()
        if not text:
            return _err(400, "Thiếu nội dung sửa", "The change is empty")
        rev = deps.task_store().team_amend(task_id, text)
        if rev is None:
            return _err(409, "Việc đã kết thúc", "The job has already ended")
        api.runner()._state(team_id)
        return {"ok": True, "revision": rev}

    @app.post("/teams/{team_id}/tasks/{task_id}/unblock")
    async def teams_task_unblock(team_id: str, task_id: str, request: Request, brain: str = "brain"):
        team, err = _team(team_id, brain)
        if err:
            return err
        if not _own_task(team_id, task_id):
            return _err(404, "Không có việc này trong nhóm", "No such job in this team")
        action = str((await _body(request)).get("action") or "resume")
        if action not in ("retry", "resume"):
            return _err(400, "Thao tác không hợp lệ", "Invalid action")
        if not api.runner().unblock(task_id, action):
            return _err(409, "Việc không ở trạng thái bị chặn", "The job is not blocked")
        api.kick()
        api.runner()._state(team_id)
        return {"ok": True}

    @app.get("/teams/{team_id}/messages")
    async def teams_messages(team_id: str, brain: str = "brain", before_ts: Optional[float] = None,
                             before_id: Optional[int] = None, limit: int = 30):
        team, err = _team(team_id, brain)
        if err:
            return err
        before = (before_ts, before_id) if before_ts is not None and before_id is not None else None
        page = await asyncio.to_thread(deps.session_store().get_team_messages_page, team["session_id"], limit, before)
        return dict(page, ok=True)

    @app.post("/teams/{team_id}/messages")
    async def teams_send(team_id: str, request: Request, brain: str = "brain"):
        team, err = _team(team_id, brain)
        if err:
            return err
        if team["status"] == "archived":
            return _err(409, "Nhóm đã lưu trữ, không gửi tin được", "The team is archived")
        body = await _body(request)
        runner = api.runner()
        try:
            sub = runner.submit(team_id, str(body.get("text") or ""), mentions=list(body.get("mentions") or []),
                                as_job=bool(body.get("as_job")), client_msg_id=str(body.get("client_msg_id") or ""))
        except TeamError as ex:
            return _team_err(ex)
        if sub["replies"]:
            api._spawn(runner.run_replies(sub))
        if sub.get("task_id") and sub["created"]:
            api.kick()
        return dict(sub, ok=True)

    @app.post("/teams/{team_id}/messages/{message_id}/accept")
    async def teams_accept(team_id: str, message_id: int, brain: str = "brain"):
        team, err = _team(team_id, brain)
        if err:
            return err
        try:
            tid = api.runner().accept_proposal(team_id, message_id)
        except TeamError as ex:
            return _team_err(ex)
        api.kick()
        return {"ok": True, "task_id": tid}

    @app.post("/teams/{team_id}/messages/{message_id}/decision")
    async def teams_decision(team_id: str, message_id: int, request: Request, brain: str = "brain"):
        team, err = _team(team_id, brain)
        if err:
            return err
        on = bool((await _body(request)).get("on", True))
        ss = deps.session_store()
        if not ss.update_team_message_meta(team["session_id"], message_id, {"decision": on}):
            return _err(404, "Không có tin này trong nhóm", "No such message in this team")
        api.runner()._publish({"type": "team_message", "team_id": team_id,
                               "message": ss.team_message(team["session_id"], message_id)})
        return {"ok": True}

    @app.get("/teams/{team_id}/turns")
    async def teams_turns(team_id: str, brain: str = "brain", since: float = 0, limit: int = 500):
        team, err = _team(team_id, brain)
        if err:
            return err
        rows = await asyncio.to_thread(api.teams().turns, team_id, since, max(1, min(int(limit), 2000)))
        return {"ok": True, "turns": rows}

    return api
