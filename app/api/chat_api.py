import uuid
import logging
from flask import Blueprint, request, jsonify
from app.database import get_db_cursor
from app.generation.rag_pipeline import RAGPipeline

logger = logging.getLogger(__name__)

chat_bp = Blueprint("chat_bp", __name__)
pipeline = RAGPipeline()


@chat_bp.route("/api/chat", methods=["POST"])
def chat():
    data = request.get_json(silent=True) or {}
    question = data.get("question", "").strip()
    conversation_id = data.get("conversation_id")
    document_ids = data.get("document_ids")  # Optional list of doc IDs to scope retrieval

    if not question:
        return jsonify({"success": False, "error": "Question cannot be empty."}), 400

    # Validate document_ids if provided
    if document_ids is not None:
        if not isinstance(document_ids, list) or not all(isinstance(d, str) for d in document_ids):
            return jsonify({"success": False, "error": "document_ids must be a list of strings."}), 400

    # Ensure conversation exists if ID provided, or create one
    if not conversation_id:
        conversation_id = str(uuid.uuid4())
        title = question[:40] + ("..." if len(question) > 40 else "")
        with get_db_cursor() as cur:
            cur.execute(
                "INSERT INTO conversations (id, title) VALUES (?, ?)",
                (conversation_id, title)
            )

    try:
        result = pipeline.process_query(
            question=question,
            conversation_id=conversation_id,
            enable_rewriting=True,
            enable_dense=True,
            enable_bm25=True,
            enable_rerank=True,
            document_ids=document_ids or []
        )
        return jsonify({
            "success": True,
            "conversation_id": conversation_id,
            "data": result
        })
    except Exception as e:
        logger.exception("Error during inference for conversation %s", conversation_id)
        return jsonify({"success": False, "error": "An internal processing error occurred."}), 500


@chat_bp.route("/api/conversations", methods=["GET"])
def list_conversations():
    with get_db_cursor() as cur:
        cur.execute(
            """
            SELECT c.id, c.title, c.created_at, COUNT(m.id) AS message_count
            FROM conversations c
            LEFT JOIN messages m ON c.id = m.conversation_id
            GROUP BY c.id
            ORDER BY c.created_at DESC
            """
        )
        convs = [dict(r) for r in cur.fetchall()]
    return jsonify({"success": True, "conversations": convs})


@chat_bp.route("/api/conversations/<conv_id>", methods=["GET"])
def get_conversation(conv_id):
    with get_db_cursor() as cur:
        cur.execute("SELECT * FROM conversations WHERE id = ?", (conv_id,))
        conv = cur.fetchone()
        if not conv:
            return jsonify({"success": False, "error": "Conversation not found."}), 404

        cur.execute(
            "SELECT id, role, content, created_at FROM messages WHERE conversation_id = ? ORDER BY created_at ASC",
            (conv_id,)
        )
        messages = [dict(r) for r in cur.fetchall()]

    return jsonify({"success": True, "conversation": dict(conv), "messages": messages})


@chat_bp.route("/api/conversations/<conv_id>", methods=["DELETE"])
def delete_conversation(conv_id):
    with get_db_cursor() as cur:
        cur.execute("DELETE FROM conversations WHERE id = ?", (conv_id,))
    return jsonify({"success": True, "message": "Conversation deleted."})


@chat_bp.route("/api/sources/<chunk_id>", methods=["GET"])
def get_source_details(chunk_id):
    with get_db_cursor() as cur:
        cur.execute(
            """
            SELECT c.*, d.filename, d.file_type
            FROM chunks c
            JOIN documents d ON c.document_id = d.id
            WHERE c.id = ?
            """,
            (chunk_id,)
        )
        chunk = cur.fetchone()
        if not chunk:
            return jsonify({"success": False, "error": "Source chunk not found."}), 404

    return jsonify({"success": True, "source": dict(chunk)})
