from flask import Blueprint, jsonify
from app.database import get_db_cursor
from app.evaluation.evaluator import Evaluator

evaluation_bp = Blueprint("evaluation_bp", __name__)
evaluator = Evaluator()


@evaluation_bp.route("/api/evaluation/run", methods=["POST"])
def run_evaluation():
    try:
        report = evaluator.run_benchmark()
        return jsonify({"success": True, "report": report})
    except Exception as e:
        return jsonify({"success": False, "error": f"Evaluation failure: {str(e)}"}), 500


@evaluation_bp.route("/api/evaluation/history", methods=["GET"])
def get_evaluation_history():
    with get_db_cursor() as cur:
        cur.execute(
            """
            SELECT id, pipeline_name, num_samples, mean_hit_rate, mean_mrr,
                   mean_faithfulness, mean_answer_relevance, mean_latency, created_at
            FROM evaluations
            ORDER BY created_at DESC
            LIMIT 20
            """
        )
        rows = [dict(r) for r in cur.fetchall()]
    return jsonify({"success": True, "history": rows})
