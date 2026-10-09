from flask import Blueprint, jsonify
from app.database import get_db_cursor

analytics_bp = Blueprint("analytics_bp", __name__)


@analytics_bp.route("/api/analytics", methods=["GET"])
def get_analytics():
    with get_db_cursor() as cur:
        # Document and chunk counts
        cur.execute("SELECT COUNT(*) AS total_docs FROM documents")
        total_docs = cur.fetchone()["total_docs"]

        cur.execute("SELECT COUNT(*) AS total_chunks FROM chunks")
        total_chunks = cur.fetchone()["total_chunks"]

        # Query metrics
        cur.execute("SELECT COUNT(*) AS total_queries FROM queries")
        total_queries = cur.fetchone()["total_queries"]

        cur.execute("SELECT AVG(retrieval_latency) AS avg_ret_lat, AVG(generation_latency) AS avg_gen_lat, AVG(total_latency) AS avg_tot_lat FROM queries")
        lat_row = cur.fetchone()
        avg_ret_lat = round(lat_row["avg_ret_lat"] or 0.0, 4)
        avg_gen_lat = round(lat_row["avg_gen_lat"] or 0.0, 4)
        avg_tot_lat = round(lat_row["avg_tot_lat"] or 0.0, 4)

        # Evidence status distribution
        cur.execute("SELECT evidence_status, COUNT(*) AS count FROM queries GROUP BY evidence_status")
        status_dist = {r["evidence_status"]: r["count"] for r in cur.fetchall()}

        # Top queried documents
        cur.execute(
            """
            SELECT d.filename, COUNT(rr.id) AS hit_count
            FROM retrieval_results rr
            JOIN chunks c ON rr.chunk_id = c.id
            JOIN documents d ON c.document_id = d.id
            GROUP BY d.filename
            ORDER BY hit_count DESC
            LIMIT 5
            """
        )
        top_docs = [dict(r) for r in cur.fetchall()]

        # Recent query volume
        cur.execute(
            """
            SELECT DATE(created_at) as query_date, COUNT(*) as query_count
            FROM queries
            GROUP BY DATE(created_at)
            ORDER BY query_date ASC
            LIMIT 7
            """
        )
        daily_volume = [dict(r) for r in cur.fetchall()]

        # User feedback metrics
        cur.execute("SELECT COUNT(*) AS total_feedback, SUM(CASE WHEN rating = 1 THEN 1 ELSE 0 END) AS helpful_count FROM feedback")
        fb_row = cur.fetchone()
        feedback_metrics = {
            "total_feedback": fb_row["total_feedback"] or 0,
            "helpful_count": fb_row["helpful_count"] or 0,
            "satisfaction_rate": round((fb_row["helpful_count"] or 0) / fb_row["total_feedback"] * 100, 1) if fb_row and fb_row["total_feedback"] else None
        }

    return jsonify({
        "success": True,
        "metrics": {
            "total_documents": total_docs,
            "total_chunks": total_chunks,
            "total_queries": total_queries,
            "avg_retrieval_latency": avg_ret_lat,
            "avg_generation_latency": avg_gen_lat,
            "avg_total_latency": avg_tot_lat,
            "evidence_status_distribution": status_dist,
            "top_queried_documents": top_docs,
            "daily_volume": daily_volume,
            "user_feedback": feedback_metrics
        }
    })


@analytics_bp.route("/api/feedback", methods=["POST"])
def submit_feedback():
    import uuid
    from flask import request
    data = request.get_json(silent=True) or {}
    query_id = data.get("query_id")
    rating = data.get("rating")
    comment = data.get("comment", "")

    if not query_id or rating not in (0, 1):
        return jsonify({"success": False, "error": "query_id and binary rating (0 or 1) are required."}), 400

    feedback_id = str(uuid.uuid4())
    try:
        with get_db_cursor() as cur:
            cur.execute(
                "INSERT INTO feedback (id, query_id, rating, comment) VALUES (?, ?, ?, ?)",
                (feedback_id, query_id, rating, comment)
            )
        return jsonify({"success": True, "feedback_id": feedback_id})
    except Exception as e:
        return jsonify({"success": False, "error": "Failed to record feedback."}), 500

