from models import Team
from routes.teams import _lock_team_for_membership_mutation
from sqlalchemy.dialects import postgresql
from sqlmodel import Session


def test_membership_mutation_locks_team_row(
    db_session: Session,
    monkeypatch,
):
    team = Team(name="Owner serialization")
    db_session.add(team)
    db_session.commit()
    db_session.refresh(team)

    statements = []
    original_exec = db_session.exec

    def capture(statement, *args, **kwargs):
        statements.append(statement)
        return original_exec(statement, *args, **kwargs)

    monkeypatch.setattr(db_session, "exec", capture)

    locked = _lock_team_for_membership_mutation(db_session, team.id)

    assert locked.id == team.id
    assert statements
    compiled = str(
        statements[0].compile(
            dialect=postgresql.dialect(),
            compile_kwargs={"literal_binds": True},
        )
    )
    assert "FOR UPDATE" in compiled
