from app.models.note import Note
from app.utils.datetime import utc_now


def test_note_create_list_update_and_soft_delete(client, auth_headers):
    headers, _ = auth_headers
    created = client.post(
        "/notes",
        headers=headers,
        json={"title": "First", "content": "<p>Hello</p>"},
    )
    assert created.status_code == 201
    note_id = created.json()["id"]
    assert client.get(f"/notes/{note_id}", headers=headers).json()["title"] == "First"

    listing = client.get("/notes", headers=headers)
    assert listing.status_code == 200
    assert listing.json()["total"] == 1
    assert listing.json()["items"][0]["id"] == note_id

    updated = client.put(
        f"/notes/{note_id}",
        headers=headers,
        json={"title": "Updated", "content": "<script>alert(1)</script><p>Safe</p>"},
    )
    assert updated.status_code == 200
    assert updated.json()["title"] == "Updated"
    assert "script" not in updated.json()["content"]

    assert client.delete(f"/notes/{note_id}", headers=headers).status_code == 204
    assert client.get(f"/notes/{note_id}", headers=headers).status_code == 404
    assert client.get("/notes", headers=headers).json()["total"] == 0


def test_note_html_is_sanitized_and_oversized_content_is_rejected(client, auth_headers):
    headers, _ = auth_headers
    response = client.post(
        "/notes",
        headers=headers,
        json={
            "title": "Safe HTML",
            "content": '<p onclick="run()">text</p><a href="javascript:run()">link</a>',
        },
    )
    assert response.status_code == 201
    assert "onclick" not in response.json()["content"]
    assert "javascript:" not in response.json()["content"]

    oversized = client.post(
        "/notes",
        headers=headers,
        json={"title": "Too large", "content": "x" * 200_001},
    )
    assert oversized.status_code == 422


def test_user_id_is_not_accepted_in_note_request(client, auth_headers):
    headers, _ = auth_headers
    response = client.post(
        "/notes",
        headers=headers,
        json={"title": "No ownership override", "user_id": 999},
    )
    assert response.status_code == 422


def test_users_only_see_and_modify_their_own_notes(
    client, db_session, users, auth_headers
):
    user_a, user_b = users
    note_a = Note(user_id=user_a.id, title="A private", content="", created_at=utc_now(), updated_at=utc_now())
    note_b = Note(user_id=user_b.id, title="B private", content="", created_at=utc_now(), updated_at=utc_now())
    db_session.add_all([note_a, note_b])
    db_session.commit()
    db_session.refresh(note_a)
    db_session.refresh(note_b)
    headers_a, headers_b = auth_headers

    assert [item["title"] for item in client.get("/notes", headers=headers_a).json()["items"]] == [
        "A private"
    ]
    assert [item["title"] for item in client.get("/notes", headers=headers_b).json()["items"]] == [
        "B private"
    ]
    for response in (
        client.get(f"/notes/{note_b.id}", headers=headers_a),
        client.put(
            f"/notes/{note_b.id}",
            headers=headers_a,
            json={"title": "Hijacked", "content": ""},
        ),
        client.delete(f"/notes/{note_b.id}", headers=headers_a),
        client.get(f"/notes/{note_a.id}", headers=headers_b),
    ):
        assert response.status_code == 404


def test_deleted_note_is_not_returned_again(client, db_session, users, auth_headers):
    user_a, _ = users
    note = Note(
        user_id=user_a.id,
        title="Deleted",
        content="",
        created_at=utc_now(),
        updated_at=utc_now(),
        deleted_at=utc_now(),
    )
    db_session.add(note)
    db_session.commit()
    db_session.refresh(note)

    headers, _ = auth_headers
    assert client.get(f"/notes/{note.id}", headers=headers).status_code == 404
    assert client.get("/notes", headers=headers).json()["total"] == 0
