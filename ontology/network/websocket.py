#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import socket
import binascii

from time import time
from sys import maxsize
from typing import List

from websockets import client
from Cryptodome.Random.random import randint, choice

from ontology.account.account import Account
from ontology.smart_contract.neo_vm import NeoVm
from ontology.core.transaction import Transaction
from ontology.exception.error_code import ErrorCode
from ontology.exception.exception import SDKException
from ontology.smart_contract.neo_contract.abi.abi_function import AbiFunction
from ontology.smart_contract.neo_contract.abi.build_params import BuildParams
from ontology.smart_contract.neo_contract.invoke_function import InvokeFunction

TEST_WS_ADDRESS = ['ws://polaris1.ont.io:20335', 'ws://polaris2.ont.io:20335', 'ws://polaris3.ont.io:20335']
MAIN_WS_ADDRESS = ['ws://dappnode1.ont.io:20335', 'ws://dappnode2.ont.io:20335']


class WebsocketClient(object):
    def __init__(self, url: str = ''):
        self.__url = url
        self.__id = 0
        self.__ws_client = None

    def __generate_ws_id(self):
        if self.__id == 0:
            self.__id = randint(0, maxsize)
        return self.__id

    def set_address(self, url: str):
        self.__url = url

    def get_address(self):
        return self.__url

    def connect_to_test_net(self):
        restful_address = choice(TEST_WS_ADDRESS)
        self.set_address(restful_address)

    def connect_to_main_net(self):
        restful_address = choice(MAIN_WS_ADDRESS)
        self.set_address(restful_address)

    async def connect(self):
        try:
            self.__ws_client = await client.connect(self.__url)
        except ConnectionAbortedError as e:
            raise SDKException(ErrorCode.other_error(e.args[1])) from None
        except socket.gaierror as e:
            raise SDKException(ErrorCode.other_error(e.args[1])) from None

    async def close_connect(self):
        if isinstance(self.__ws_client, client.WebSocketClientProtocol) and not self.__ws_client.closed:
            await self.__ws_client.close()

    async def __send_recv(self, msg: dict, is_full: bool):
        if self.__ws_client is None or self.__ws_client.closed:
            await self.connect()
        await self.__ws_client.send(json.dumps(msg))
        response = await self.__ws_client.recv()
        response = json.loads(response)
        if is_full:
            return response
        if response['Error'] != 0:
            raise SDKException(ErrorCode.other_error(response.get('Result', '')))
        return response.get('Result', dict())

    async def send_heartbeat(self, is_full: bool = False):
        if self.__id == 0:
            self.__id = self.__generate_ws_id()
        msg = dict(Action='heartbeat', Version='V1.0.0', Id=self.__id)
        return await self.__send_recv(msg, is_full)

    async def get_connection_count(self, is_full: bool = False) -> int:
        if self.__id == 0:
            self.__id = self.__generate_ws_id()
        msg = dict(Action='getconnectioncount', Id=self.__id, Version='1.0.0')
        return await self.__send_recv(msg, is_full)

    async def get_session_count(self, is_full: bool = False):
        if self.__id == 0:
            self.__id = self.__generate_ws_id()
        msg = dict(Action='getsessioncount', Id=self.__id, Version='1.0.0')
        return await self.__send_recv(msg, is_full)

    async def get_balance(self, b58_address: str, is_full: bool = False):
        if self.__id == 0:
            self.__id = self.__generate_ws_id()
        msg = dict(Action='getbalance', Id=self.__id, Version='1.0.0', Addr=b58_address)
        response = await self.__send_recv(msg, is_full=True)
        response['Result'] = dict((k, int(v)) for k, v in response['Result'].items())
        if is_full:
            return response
        return response['Result']

    async def get_merkle_proof(self, tx_hash: str, is_full: bool = False):
        if self.__id == 0:
            self.__id = self.__generate_ws_id()
        msg = dict(Action='getmerkleproof', Id=self.__id, Version='1.0.0', Hash=tx_hash, Raw=0)
        return await self.__send_recv(msg, is_full)

    async def get_storage(self, hex_contract_address: str, key: str, is_full: bool = False):
        if self.__id == 0:
            self.__id = self.__generate_ws_id()
        msg = dict(Action='getstorage', Id=self.__id, Version='1.0.0', Hash=hex_contract_address, Key=key)
        return await self.__send_recv(msg, is_full)

    async def get_smart_contract(self, hex_contract_address: str, is_full: bool = False):
        if self.__id == 0:
            self.__id = self.__generate_ws_id()
        msg = dict(Action='getcontract', Id=self.__id, Version='1.0.0', Hash=hex_contract_address, Raw=0)
        response = await self.__send_recv(msg, is_full=True)
        if is_full:
            return response
        return response['Result']

    async def get_smart_contract_event_by_tx_hash(self, tx_hash: str, is_full: bool = False) -> dict:
        if self.__id == 0:
            self.__id = self.__generate_ws_id()
        msg = dict(Action='getsmartcodeeventbyhash', Id=self.__id, Version='1.0.0', Hash=tx_hash, Raw=0)
        return await self.__send_recv(msg, is_full)

    async def get_smart_contract_event_by_height(self, height: int, is_full: bool = False):
        if self.__id == 0:
            self.__id = self.__generate_ws_id()
        msg = dict(Action='getsmartcodeeventbyheight', Id=self.__id, Version='1.0.0', Height=height)
        return await self.__send_recv(msg, is_full)

    async def get_block_height(self, is_full: bool = False) -> dict:
        if self.__id == 0:
            self.__id = self.__generate_ws_id()
        msg = dict(Action='getblockheight', Id=self.__id, Version='1.0.0')
        return await self.__send_recv(msg, is_full)

    async def get_block_height_by_tx_hash(self, tx_hash: str, is_full: bool = False):
        if self.__id == 0:
            self.__id = self.__generate_ws_id()
        msg = dict(Action='getblockheightbytxhash', Id=self.__id, Version='1.0.0', Hash=tx_hash)
        return await self.__send_recv(msg, is_full)

    async def get_block_hash_by_height(self, height: int, is_full: bool = False):
        if self.__id == 0:
            self.__id = self.__generate_ws_id()
        msg = dict(Action='getblockhash', Id=self.__id, Version='1.0.0', Height=height)
        return await self.__send_recv(msg, is_full)

    async def get_block_by_height(self, height: int, is_full: bool = False) -> dict:
        if self.__id == 0:
            self.__id = self.__generate_ws_id()
        msg = dict(Action='getblockbyheight', Version='1.0.0', Id=self.__id, Raw=0, Height=height)
        return await self.__send_recv(msg, is_full)

    async def get_block_by_hash(self, block_hash: str, is_full: bool = False) -> dict:
        if self.__id == 0:
            self.__id = self.__generate_ws_id()
        msg = dict(Action='getblockbyhash', Version='1.0.0', Id=self.__id, Hash=block_hash)
        return await self.__send_recv(msg, is_full)

    async def subscribe(self, contract_address_list: List[str] or str, is_event: bool = False,
                        is_json_block: bool = False,
                        is_raw_block: bool = False, is_tx_hash: bool = False, is_full: bool = False) -> dict:
        if self.__id == 0:
            self.__id = self.__generate_ws_id()
        if isinstance(contract_address_list, str):
            contract_address_list = [contract_address_list]
        msg = dict(Action='subscribe', Version='1.0.0', Id=self.__id, ConstractsFilter=contract_address_list,
                   SubscribeEvent=is_event, SubscribeJsonBlock=is_json_block, SubscribeRawBlock=is_raw_block,
                   SubscribeBlockTxHashs=is_tx_hash)
        return await self.__send_recv(msg, is_full)

    async def recv_subscribe_info(self, is_full: bool = False):
        response = await self.__ws_client.recv()
        response = json.loads(response)
        if is_full:
            return response
        if response['Error'] != 0:
            raise SDKException(ErrorCode.other_error(response.get('Result', '')))
        return response.get('Result', dict())

    async def send_raw_transaction(self, tx: Transaction, is_full: bool = False):
        tx_data = tx.serialize(is_hex=True).decode('ascii')
        msg = dict(Action='sendrawtransaction', Version='1.0.0', Id=self.__id, PreExec='0', Data=tx_data)
        return await self.__send_recv(msg, is_full)

    async def send_raw_transaction_pre_exec(self, tx: Transaction, is_full: bool = False):
        tx_data = tx.serialize(is_hex=True).decode('ascii')
        msg = dict(Action='sendrawtransaction', Version='1.0.0', Id=self.__id, PreExec='1', Data=tx_data)
        return await self.__send_recv(msg, is_full)

    async def send_neo_vm_transaction(self, contract_address: str or bytes or bytearray, acct: Account,
                                      payer_acct: Account, gas_limit: int, gas_price: int,
                                      func: AbiFunction or InvokeFunction, pre_exec: bool, is_full: bool = False):
        if isinstance(func, AbiFunction):
            params = BuildParams.serialize_abi_function(func)
        elif isinstance(func, InvokeFunction):
            params = func.create_invoke_code()
        else:
            raise SDKException(ErrorCode.other_error('the type of func is error.'))
        if isinstance(contract_address, str) and len(contract_address) == 40:
            contract_address = bytearray(binascii.a2b_hex(contract_address))
            contract_address.reverse()
        if pre_exec:
            if isinstance(contract_address, bytes):
                tx = NeoVm.make_invoke_transaction(bytearray(contract_address), bytearray(params), b'', 0, 0)
            elif isinstance(contract_address, bytearray):
                tx = NeoVm.make_invoke_transaction(contract_address, bytearray(params), b'', 0, 0)
            else:
                raise SDKException(ErrorCode.param_err('the data type of contract address is incorrect.'))
            if acct is not None:
                tx.sign_transaction(acct)
            return self.send_raw_transaction_pre_exec(tx, is_full)
        else:
            unix_time_now = int(time())
            params.append(0x67)
            for i in contract_address:
                params.append(i)
            if payer_acct is None:
                raise SDKException(ErrorCode.param_err('payer account is None.'))
            tx = Transaction(0, 0xd1, unix_time_now, gas_price, gas_limit, payer_acct.get_address().to_bytes(),
                             params, bytearray(), [])
            tx.sign_transaction(payer_acct)
            if isinstance(acct, Account) and acct.get_address_base58() != payer_acct.get_address_base58():
                tx.add_sign_transaction(acct)
            return await self.send_raw_transaction(tx, is_full)
