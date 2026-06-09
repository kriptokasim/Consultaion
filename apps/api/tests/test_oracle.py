from uuid import uuid4
from models import User, OracleSession, OracleBranch
from sqlmodel import Session, select
import pytest
from routes.oracle import run_base_reasoning_task, run_fork_reasoning_task

def test_start_oracle_session_endpoint(authenticated_client, db_session: Session):
    payload = {
        "prompt": "Evaluate the scalability of local RAM caching under peak concurrency."
    }
    response = authenticated_client.post('/oracle', json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "session_id" in data
    assert "root_branch_id" in data
    assert data["prompt"] == "Evaluate the scalability of local RAM caching under peak concurrency."
    assert data["status"] == "running"

    # Verify session is persisted
    db_session.expire_all()
    session_id = data["session_id"]
    sess = db_session.get(OracleSession, session_id)
    assert sess is not None
    assert sess.prompt == "Evaluate the scalability of local RAM caching under peak concurrency."


def test_get_oracle_session_endpoint(authenticated_client, db_session: Session):
    user = db_session.exec(select(User).where(User.email == 'normal@example.com')).first()
    sess = OracleSession(
        id=str(uuid4()),
        user_id=user.id,
        prompt="Query on compliance.",
        status="completed"
    )
    db_session.add(sess)
    db_session.commit()

    branch = OracleBranch(
        id=str(uuid4()),
        session_id=sess.id,
        parent_branch_id=None,
        assumption_text="Base reasoning summary",
        reasoning_nodes={
            "nodes": [
                {
                    "id": "node_1",
                    "title": "First Step",
                    "type": "observation",
                    "content": "Analyze compliance."
                }
            ]
        }
    )
    db_session.add(branch)
    db_session.commit()

    response = authenticated_client.get(f'/oracle/{sess.id}')
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == sess.id
    assert data["status"] == "completed"
    assert len(data["branches"]) == 1
    assert data["branches"][0]["id"] == branch.id
    assert data["branches"][0]["nodes"][0]["title"] == "First Step"


@pytest.mark.asyncio
async def test_oracle_background_reasoning_tasks(authenticated_client, db_session: Session):
    user = db_session.exec(select(User).where(User.email == 'normal@example.com')).first()
    sess = OracleSession(
        id=str(uuid4()),
        user_id=user.id,
        prompt="Query on operations.",
        status="running"
    )
    db_session.add(sess)
    
    root_branch = OracleBranch(
        id=str(uuid4()),
        session_id=sess.id,
        parent_branch_id=None,
        assumption_text="Base reasoning summary",
        reasoning_nodes=None
    )
    db_session.add(root_branch)
    db_session.commit()

    # 1. Run base reasoning background task
    await run_base_reasoning_task(sess.id, root_branch.id, sess.prompt)

    db_session.expire_all()
    updated_sess = db_session.get(OracleSession, sess.id)
    updated_branch = db_session.get(OracleBranch, root_branch.id)
    assert updated_sess.status == "completed"
    assert updated_branch.reasoning_nodes is not None
    assert len(updated_branch.reasoning_nodes["nodes"]) > 0

    # 2. Run fork reasoning background task
    fork_branch_id = str(uuid4())
    child_branch = OracleBranch(
        id=fork_branch_id,
        session_id=sess.id,
        parent_branch_id=root_branch.id,
        assumption_text="What if operations are outsourced?",
        reasoning_nodes=None
    )
    db_session.add(child_branch)
    db_session.commit()

    await run_fork_reasoning_task(
        sess.id,
        fork_branch_id,
        root_branch.id,
        updated_branch.reasoning_nodes["nodes"][0]["id"], # fork after first node
        "What if operations are outsourced?"
    )

    db_session.expire_all()
    updated_child = db_session.get(OracleBranch, fork_branch_id)
    assert updated_child.reasoning_nodes is not None
    nodes = updated_child.reasoning_nodes["nodes"]
    assert len(nodes) > 1
    # First node should match parent node
    assert nodes[0]["id"] == updated_branch.reasoning_nodes["nodes"][0]["id"]
    # Fork assumption node should be in there
    fork_nodes = [n for n in nodes if n.get("title") == "What-If Branch"]
    assert len(fork_nodes) > 0
