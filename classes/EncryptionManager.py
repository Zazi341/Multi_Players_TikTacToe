from cryptography.fernet import Fernet

class EncryptionManager:
    def __init__(self):
        # Generate a key and save it within the class.
        # In a real application, you might want to load this from a secure location.
        self.key = b'X72X9_K6ckUWWF9W0yoDBRT1ZfmNt_nH2SOeDZU-M9U='
        self.cipher = Fernet(self.key)

    def encrypt_message(self, message):
        # Ensure message is a byte string
        if isinstance(message, str):
            message = message.encode()
        encrypted_message = self.cipher.encrypt(message)
        return encrypted_message.decode('utf-8')

    def decrypt_message(self, encrypted_message):
        # Ensure encrypted_message is a byte string
        if isinstance(encrypted_message, str):
            encrypted_message = encrypted_message.encode()
        decrypted_message = self.cipher.decrypt(encrypted_message)
        return decrypted_message.decode('utf-8')
