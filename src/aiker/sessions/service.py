from __future__ import annotations

from sqlmodel import Session as DBSession

from aiker.db.repositories import create_session, get_project_by_id


def start_session(db: DBSession, project_id: int, goal: str, operator_name: str):
    project = get_project_by_id(db, project_id)
    if project is None:
        raise ValueError(f"Project id {project_id} does not exist.")
    return create_session(db=db, project_id=project_id, goal=goal, operator_name=operator_name)
