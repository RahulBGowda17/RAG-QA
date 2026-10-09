from flask import Blueprint, request, jsonify
from app.database import get_db_cursor
from app.ingestion.document_manager import DocumentManager
from app.ingestion.validator import ValidationError

documents_bp = Blueprint("documents_bp", __name__)


@documents_bp.route("/api/documents/upload", methods=["POST"])
def upload_document():
    if "file" not in request.files:
        return jsonify({"success": False, "error": "No file part in request."}), 400

    file = request.files["file"]
    if not file.filename:
        return jsonify({"success": False, "error": "No file selected."}), 400

    try:
        file_bytes = file.read()
        doc_info = DocumentManager.ingest_document(file.filename, file_bytes)
        return jsonify({"success": True, "document": doc_info}), 201
    except ValidationError as ve:
        return jsonify({"success": False, "error": str(ve)}), 400
    except ValueError as ve:
        return jsonify({"success": False, "error": str(ve)}), 409
    except Exception as e:
        return jsonify({"success": False, "error": f"Failed to ingest document: {str(e)}"}), 500


@documents_bp.route("/api/documents", methods=["GET"])
def list_documents():
    with get_db_cursor() as cur:
        cur.execute(
            """
            SELECT 
                d.id, d.filename, d.file_type, d.file_size, d.page_count, d.status,
                d.error_message, d.created_at,
                COUNT(c.id) AS chunk_count
            FROM documents d
            LEFT JOIN chunks c ON d.id = c.document_id
            GROUP BY d.id
            ORDER BY d.created_at DESC
            """
        )
        rows = [dict(r) for r in cur.fetchall()]
    return jsonify({"success": True, "documents": rows})


@documents_bp.route("/api/documents/<doc_id>", methods=["GET"])
def get_document(doc_id):
    with get_db_cursor() as cur:
        cur.execute("SELECT * FROM documents WHERE id = ?", (doc_id,))
        doc = cur.fetchone()
        if not doc:
            return jsonify({"success": False, "error": "Document not found."}), 404

        cur.execute(
            """
            SELECT id, chunk_index, page_number, section, text, token_count
            FROM chunks
            WHERE document_id = ?
            ORDER BY chunk_index ASC
            """,
            (doc_id,)
        )
        chunks = [dict(r) for r in cur.fetchall()]

    return jsonify({"success": True, "document": dict(doc), "chunks": chunks})


@documents_bp.route("/api/documents/<doc_id>", methods=["DELETE"])
def delete_document(doc_id):
    try:
        DocumentManager.delete_document(doc_id)
        return jsonify({"success": True, "message": "Document deleted and index updated."})
    except ValueError as ve:
        return jsonify({"success": False, "error": str(ve)}), 404
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@documents_bp.route("/api/documents/<doc_id>/index", methods=["POST"])
@documents_bp.route("/api/documents/<doc_id>/reindex", methods=["POST"])
def reindex_document(doc_id):
    try:
        res = DocumentManager.reindex_document(doc_id)
        return jsonify({"success": True, "message": "Document successfully reindexed.", "document": res})
    except ValueError as ve:
        return jsonify({"success": False, "error": str(ve)}), 404
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@documents_bp.route("/api/documents/rebuild", methods=["POST"])
def rebuild_all_indices():
    try:
        DocumentManager.rebuild_indices()
        return jsonify({"success": True, "message": "All indices successfully rebuilt from database chunks."})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500
