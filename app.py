from flask import Flask, request, jsonify
import requests
from datetime import datetime, timedelta

app = Flask(__name__)

# 配置常量
USDT_CONTRACT = "0x55d398326f99059fF775485246999027B3197955"
BASE_URL = "https://api.bscscan.com/api"
API_KEY = "xxxxx"



def get_block_by_time(timestamp, closest="before"):
    params = {
        "module": "block",
        "action": "getblocknobytime",
        "timestamp": str(timestamp),
        "closest": closest,
        "apikey": API_KEY
    }
    resp = requests.get(BASE_URL, params=params)
    data = resp.json()
    if data["status"] == "1":
        return int(data["result"])
    else:
        print(f"获取区块失败: {data['message']}")
        return None


def get_usdt_transactions(address, start_block, end_block):
    params = {
        "module": "account",
        "action": "tokentx",
        "contractaddress": USDT_CONTRACT,
        "address": address,
        "startblock": start_block,
        "endblock": end_block,
        "sort": "asc",
        "apikey": API_KEY
    }
    resp = requests.get(BASE_URL, params=params)
    data = resp.json()
    if data["status"] == "1":
        return data["result"]
    else:
        print(f"查询交易失败: {data['message']}")
        return []


def analyze_transactions(txs, address, min_amount=50):
    cleaned_txs = []
    for tx in txs:
        value = int(tx["value"]) / (10 ** int(tx["tokenDecimal"]))
        if value < min_amount:
            continue

        tx["amount"] = value
        tx["is_income"] = (tx["to"].lower() == address.lower())
        tx["gas_fee_bnb"] = int(tx["gasUsed"]) * int(tx["gasPrice"]) / 1e18
        tx["datetime"] = datetime.utcfromtimestamp(int(tx["timeStamp"]))
        cleaned_txs.append(tx)
    return cleaned_txs


def find_matched_pairs_with_fees_and_time(txs, max_diff=100, max_minutes=30):
    matched_pairs = []
    total_fee_bnb = 0
    total_diff_usdt = 0
    i = 0

    while i < len(txs) - 1:
        out_tx = txs[i]
        in_tx = txs[i + 1]

        if not out_tx["is_income"] and in_tx["is_income"]:
            amount_diff = abs(out_tx["amount"] - in_tx["amount"])
            time_diff = (in_tx["datetime"] - out_tx["datetime"]).total_seconds() / 60  # 分钟

            if amount_diff <= max_diff and time_diff <= max_minutes:
                fee = out_tx["gas_fee_bnb"] + in_tx["gas_fee_bnb"]
                matched_pairs.append({
                    "out_tx": out_tx,
                    "in_tx": in_tx,
                    "fee": fee,
                    "amount_diff": amount_diff,
                    "time_diff_minutes": time_diff
                })
                total_fee_bnb += fee
                total_diff_usdt += amount_diff
                i += 2
                continue
        i += 1

    return {
        "matched_pairs": matched_pairs,
        "total_fee_bnb": total_fee_bnb,
        "total_diff_usdt": total_diff_usdt
    }


@app.route('/api/analyze_usdt_transactions', methods=['GET'])
def analyze_usdt_transactions():
    # 获取查询参数
    address = request.args.get('address')
    start_date_str = request.args.get('start_date')
    end_date_str = request.args.get('end_date')
    min_amount = float(request.args.get('min_amount', 50))
    max_diff = float(request.args.get('max_diff', 100))
    max_minutes = float(request.args.get('max_minutes', 30))

    # 验证参数
    if not address or not start_date_str or not end_date_str:
        return jsonify({"error": "Missing required parameters: address, start_date, end_date"}), 400

    try:
        start_date = datetime.strptime(start_date_str, "%Y-%m-%d")
        end_date = datetime.strptime(end_date_str, "%Y-%m-%d")
    except ValueError:
        return jsonify({"error": "Invalid date format. Please use YYYY-MM-DD format."}), 400

    # 结束时间改为当天23:59:59，包含整天数据
    end_date = end_date.replace(hour=23, minute=59, second=59)

    start_ts = int(start_date.timestamp())
    end_ts = int(end_date.timestamp())

    # 获取区块范围
    start_block = get_block_by_time(start_ts)
    end_block = get_block_by_time(end_ts)

    if start_block is None or end_block is None:
        return jsonify({"error": "Failed to get block numbers for the given time range"}), 500

    # 获取交易数据
    txs = get_usdt_transactions(address, start_block, end_block)

    if not txs:
        return jsonify({"message": "No transactions found in the specified time range"}), 200

    # 分析交易数据
    cleaned_txs = analyze_transactions(txs, address, min_amount)

    if not cleaned_txs:
        return jsonify({"message": "No transactions meet the minimum amount criteria"}), 200

    # 查找匹配的交易对
    result = find_matched_pairs_with_fees_and_time(cleaned_txs, max_diff, max_minutes)

    # 准备响应数据
    response = {
        "address": address,
        "start_date": start_date_str,
        "end_date": end_date_str,
        "total_matched_pairs": len(result["matched_pairs"]),
        "total_fee_bnb": result["total_fee_bnb"],
        "total_diff_usdt": result["total_diff_usdt"],
        "matched_pairs": []
    }

    # 格式化匹配的交易对
    for pair in result["matched_pairs"]:
        out_tx = pair["out_tx"]
        in_tx = pair["in_tx"]
        response["matched_pairs"].append({
            "out_tx": {
                "hash": out_tx["hash"],
                "datetime": out_tx["datetime"].isoformat(),
                "amount": out_tx["amount"],
                "gas_fee_bnb": out_tx["gas_fee_bnb"]
            },
            "in_tx": {
                "hash": in_tx["hash"],
                "datetime": in_tx["datetime"].isoformat(),
                "amount": in_tx["amount"],
                "gas_fee_bnb": in_tx["gas_fee_bnb"]
            },
            "amount_diff": pair["amount_diff"],
            "time_diff_minutes": pair["time_diff_minutes"],
            "fee": pair["fee"]
        })

    return jsonify(response)


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
