from flask import Flask, jsonify, request
import calculate_path as calculate_path
from get_matrix import matrix
import utils
from dotenv import load_dotenv
import os
from waitress import serve
from flask_cors import CORS
from web3 import Web3
import redis
import json

app = Flask(__name__)
CORS(app)
REDIS = redis.Redis(host='redis', port=6379, decode_responses=True)

def authenticate_api_key(api_key):
    load_dotenv()
    return api_key == os.getenv('API_KEY')


@app.route('/get_path', methods=['GET'])
def get_path():
    
    token0 = request.args.get('token0') 
    token1 = request.args.get('token1') 
    amount_in = request.args.get('amount_in')

    if token0 == None or token1 == None or amount_in == None:
        response =  jsonify({'Error' : 'Missing required argument'})
        response.headers.add("Access-Control-Allow-Origin", "*")

        return response, 422
    
    try:
        amount_in = int(amount_in)
        token0 = Web3.toChecksumAddress(token0)
        token1 = Web3.toChecksumAddress(token1)
    except:
        response = jsonify({'Error' : 'Incorrect input'})
        response.headers.add("Access-Control-Allow-Origin", "*")

        return response, 422

    try:
        result = calculate_path.get_path(token0, token1, amount_in)
    
    except Exception as ex:
        response = jsonify({'Error' : 'Incorrect Amount In value', 'Router.getAmountsOut': str(ex)})
        response.headers.add("Access-Control-Allow-Origin", "*")

        return response, 422
    

    if result == None:
        response =  jsonify({'Error' : 'Pair not found'})
        response.headers.add("Access-Control-Allow-Origin", "*")

        return response, 404

    response =  jsonify({'Path': result})
    response.headers.add("Access-Control-Allow-Origin", "*")
    
    return response, 200

@app.route('/get_pairs', methods=['GET'])
def get_pairs():
    data = utils.get_pairs_data()
    prepared_data = [{"pair_address": address, 'pair_data': data} for address, data in data.items()]

    response = jsonify(prepared_data)
    response.headers.add("Access-Control-Allow-Origin", "*")

    return response, 200

@app.route('/get_tokens', methods=['GET'])
def get_tokens():
    response = jsonify(utils.get_tokens())
    response.headers.add("Access-Control-Allow-Origin", "*")

    return response, 200

@app.route('/get_tokens_data', methods=['GET'])
def get_tokens_data():
    response = jsonify(utils.get_tokens_data())
    response.headers.add("Access-Control-Allow-Origin", "*")

    return response, 200


@app.route('/add_to_blacklist', methods=['GET'])
def add_to_blacklist():

    token = request.args.get('token') 

    response = jsonify(utils.add_to_blacklist(token=token))
    response.headers.add("Access-Control-Allow-Origin", "*")

    return response, 200


@app.route('/remove_from_blacklist', methods=['GET'])
def remove_from_blacklist():

    token = request.args.get('token') 

    response = jsonify(utils.remove_from_blacklist(token=token))
    response.headers.add("Access-Control-Allow-Origin", "*")

    return response, 200

if __name__ == '__main__':
    matrix.start_matrix_updater()
    serve(app, host = "0.0.0.0", port=5001, threads = 4)
    # app.run()
