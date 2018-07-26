from ontology.wallet.wallet import WalletData
from ontology.utils.util import is_file_exist
from ontology.crypto.SignatureScheme import SignatureScheme
from datetime import datetime
import json
import base64
from collections import namedtuple
from ontology.crypto.scrypt import Scrypt
from ontology.account.account import Account
from ontology.wallet.account import AccountData, AccountInfo
from ontology.wallet.control import ProtectedKey, Control
from ontology.common.address import Address
import uuid
from ontology.wallet.identity import Identity, did_ont, IdentityInfo
from ontology.utils.util import hex_to_bytes, get_random_bytes


class WalletManager(object):
    def __init__(self, wallet_path, scheme=SignatureScheme.SHA256withECDSA):
        self.wallet_path = wallet_path
        self.scheme = scheme
        self.wallet_file = WalletData()
        self.wallet_in_mem = WalletData()

    def open_wallet(self):
        if is_file_exist(self.wallet_path) is False:
            # create a new wallet file
            self.wallet_file.create_time = datetime.today().strftime("%Y-%m-%d %H:%M:%S")
            self.wallet_file.save(self.wallet_path)
        # wallet file exists now
        self.wallet_file = self.load(self.wallet_path)
        self.wallet_in_mem = self.wallet_file
        return self.wallet_file

    def load(self, wallet_path):
        r = json.load(open(wallet_path, "r"), object_hook=lambda d: namedtuple('X', d.keys())(*d.values()))
        scrypt = Scrypt(r.scrypt.n, r.scrypt.r, r.scrypt.p, r.scrypt.dk_len)
        identities = []
        for index in range(len(r.identities)):
            prot = ProtectedKey(r.identities[index].controls[0].protected_key.address,
                                r.identities[index].controls[0].protected_key.enc_alg,
                                r.identities[index].controls[0].protected_key.key,
                                r.identities[index].controls[0].protected_key.algorithm,
                                r.identities[index].controls[0].protected_key.salt,
                                r.identities[index].controls[0].protected_key.hash_value,
                                r.identities[index].controls[0].protected_key.param)
            c = [Control(r.identities[index].controls[0].id, r.identities[index].controls[0].publicKey, prot)]
            temp = Identity(r.identities[index].ontid, r.identities[index].label, r.identities[index].lock, c,
                            r.identities[index].extra, r.identities[index].is_default)
            identities.append(temp)
        accounts = []
        for index in range(len(r.accounts)):
            prot = ProtectedKey(r.accounts[index].protected_key.address,
                                r.accounts[index].protected_key.enc_alg,
                                r.accounts[index].protected_key.key,
                                r.accounts[index].protected_key.algorithm,
                                r.accounts[index].protected_key.salt,
                                r.accounts[index].protected_key.hash_value,
                                r.accounts[index].protected_key.param)
            temp = AccountData(prot, r.accounts[index].label, r.accounts[index].public_key,
                               r.accounts[index].sign_scheme, r.accounts[index].is_default, r.accounts[index].lock)
            accounts.append(temp)

        res = WalletData(r.name, r.version, r.create_time, r.default_ontid, r.default_account_address, scrypt,
                         identities, accounts, r.extra)

        return res

    def save(self, wallet_path):
        json.dump(self.wallet_in_mem, open(wallet_path, "w"), default=lambda obj: obj.__dict__, indent=4)

    def get_wallet(self):
        return self.wallet_in_mem

    def write_wallet(self):
        self.wallet_in_mem.save(self.wallet_path)
        self.wallet_file = self.wallet_in_mem
        return self.wallet_file

    def reset_wallet(self):
        self.wallet_in_mem = self.wallet_file.clone()
        return self.wallet_in_mem

    def get_signature_scheme(self):
        return self.scheme

    def set_signature_scheme(self, scheme):
        self.scheme = scheme

    def import_identity(self, label: str, encrypted_privkey: str, pwd, salt: bytearray, address: str):
        encrypted_privkey = base64.decodebytes(encrypted_privkey.encode())
        private_key = Account.get_gcm_decoded_private_key(encrypted_privkey, pwd, address, salt,
                                                          Scrypt().get_n(),
                                                          self.scheme)

        info = self.create_identity(label, pwd, salt, private_key)
        private_key = None
        for index in range(len(self.wallet_in_mem.identities)):
            if self.wallet_in_mem.identities[index].ontid == info.ontid:
                return self.wallet_in_mem.identities[index]
        return None

    def create_identity(self, label: str, pwd, salt, private_key):
        acct = self.create_account(label, pwd, salt, private_key, False)
        info = IdentityInfo()
        info.ontid = did_ont + Address.address_from_bytes_pubkey(acct.get_address().to_array()).to_base58()
        info.pubic_key = acct.serialize_public_key().hex()
        info.private_key = acct.serialize_private_key().hex()
        info.prikey_wif = acct.export_wif()
        info.encrypted_prikey = acct.export_gcm_encrypted_private_key(pwd, salt, Scrypt().get_n())
        info.address_u160 = acct.get_address().to_array().hex()
        return info

    def create_identity_from_prikey(self, pwd, private_key):
        info = self.create_identity("", pwd, hex_to_bytes(private_key))
        private_key = None
        for index in range(len(self.wallet_in_mem.identities)):
            if self.wallet_in_mem.identities[index].ontid == info.ontid:
                return self.wallet_in_mem.identities[index]
        return None

    def create_account(self, label, pwd, salt, priv_key, account_flag: bool):
        account = Account(priv_key, self.scheme)
        # initialization
        if self.scheme == SignatureScheme.SHA256withECDSA:
            prot = ProtectedKey(algorithm="ECDSA", enc_alg="aes-256-gcm", hash_value="SHA256withECDSA",
                                param={"curve": "secp256r1"})
            acct = AccountData(protected_key=prot, sign_scheme="SHA256withECDSA")
        else:
            raise ValueError("scheme type is error")
        # set key
        if pwd != None:
            acct.protected_key.key = account.export_gcm_encrypted_private_key(pwd, salt, Scrypt().get_n()).decode()
            pwd = None
        else:
            acct.protected_key.key = account.serialize_private_key().hex()

        acct.protected_key.address = Address.address_from_bytes_pubkey(
            account.get_address().to_array()).to_base58()
        # set label
        if label == None or label == "":
            label = str(uuid.uuid4())[0:8]
        if account_flag:
            for index in range(len(self.wallet_in_mem.accounts)):
                if acct.protected_key.address == self.wallet_in_mem.accounts[index].protected_key.address:
                    raise ValueError("wallet account exists")

            if len(self.wallet_in_mem.accounts) == 0:
                acct.is_default = True
                self.wallet_in_mem.default_account_address = acct.protected_key.address
            acct.label = label
            acct.protected_key.salt = salt.hex()
            self.wallet_in_mem.accounts.append(acct)
        else:
            print(type(self.wallet_in_mem))
            for index in range(len(self.wallet_in_mem.identities)):
                if self.wallet_in_mem.identities[index].ontid == did_ont + acct.protected_key.address:
                    raise ValueError("wallet identity exists")

        idt = Identity()
        idt.ontid = did_ont + acct.protected_key.address
        idt.label = label
        if len(self.wallet_in_mem.identities) == 0:
            idt.is_default = True
            self.wallet_in_mem.default_ontid = idt.ontid
        prot = ProtectedKey(key=acct.protected_key.key, algorithm="ECDSA", param={"curve": "secp256r1"},
                            salt=salt.hex(),
                            address=acct.protected_key.address)
        ctl = Control(id="keys-1", protected_key=prot)
        idt.controls.append(ctl)
        self.wallet_in_mem.identities.append(idt)
        return account

    def import_account(self, label, encrypted_prikey, pwd, address, salt):
        private_key = Account.get_gcm_decoded_private_key(encrypted_prikey, pwd, address, salt, Scrypt().get_n(),
                                                          self.scheme)
        info = self.create_account_info(label, pwd, salt, hex_to_bytes(private_key))
        private_key, pwd = None, None
        for index in range(len(self.wallet_in_mem.accounts)):
            if info.address_base58 == self.wallet_in_mem.accounts[index].protected_key.address:
                return self.wallet_in_mem.accounts[index]
        return None

    def create_account_info(self, label, pwd, salt, private_key):
        acct = self.create_account(label, pwd, salt, private_key, True)
        info = AccountInfo()
        info.address_base58 = Address.address_from_bytes_pubkey(acct.serialize_public_key()).to_base58()
        info.public_key = acct.serialize_public_key().hex()
        info.private_key = acct.serialize_private_key().hex()
        info.prikey_wif = acct.export_wif()
        info.encrypted_prikey = acct.export_gcm_encrypted_private_key(pwd, salt, Scrypt().get_n())
        info.address_u160 = acct.get_address().to_array().hex()
        return info

    def create_account_from_prikey(self, pwd, private_key):
        salt = get_random_bytes(16)
        info = self.create_account_info("", pwd, salt, hex_to_bytes(private_key))
        for index in range(len(self.wallet_in_mem.accounts)):
            if info.address_base58 == self.wallet_in_mem.accounts[index].protected_key.address:
                return self.wallet_in_mem.accounts[index]
        return None

    def get_account_by_address(self, address: Address, pwd, salt):
        for index in range(len(self.wallet_in_mem.accounts)):
            if self.wallet_in_mem.accounts[index].protected_key.address == address.to_base58():
                key = self.wallet_in_mem.accounts[index].protected_key.key
                addr = self.wallet_in_mem.accounts[index].protected_key.address
                private_key = Account.get_gcm_decoded_private_key(key, pwd, addr, salt, Scrypt().get_n(), self.scheme)
                return Account(hex_to_bytes(private_key), self.scheme)

        for index in range(len(self.wallet_in_mem.identities)):
            if self.wallet_in_mem.identities[index].ontid == did_ont + address.to_base58():
                addr = self.wallet_in_mem.identities[index].ontid.replace(did_ont, "")
                key = self.wallet_in_mem.identities[index].controls[0].key
                private_key = Account.get_gcm_decoded_private_key(key, pwd, addr, salt, Scrypt().get_n(), self.scheme)
                return Account(hex_to_bytes(private_key), self.scheme)
        return None


if __name__ == '__main__':
    # test wallet load and save
    private_key = '99bbd375c745088b372c6fc2ab38e2fb6626bc552a9da47fc3d76baa21537a1c'
    wallet_path = '/Users/zhaoxavi/test.txt'
    w = WalletManager(wallet_path=wallet_path)
    w.open_wallet()
    print(w.wallet_in_mem)
    salt = get_random_bytes(16)
    #w.create_account("123", "567", salt, private_key, True)
    print(type(w.wallet_in_mem.accounts[0].protected_key.param))
    w.save(wallet_path)
