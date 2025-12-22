from flask import Blueprint, jsonify

credits_bp = Blueprint("credits", __name__)


@credits_bp.get("/balance")
def balance():
    """返回示例积分余额。"""
    return jsonify({"balance": 1200})


@credits_bp.get("/transactions")
def transactions():
    """返回示例积分流水。"""
    sample = [
        {"id": "txn-1", "type": "recharge", "amount": 500, "description": "新手奖励"},
        {"id": "txn-2", "type": "consume", "amount": -50, "description": "TTS 消耗"},
    ]
    return jsonify({"transactions": sample, "total": len(sample)})

