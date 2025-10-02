import logging
import subprocess
import secrets
import string
from typing import Tuple, Optional
from config import WIREGUARD_ENDPOINT, WIREGUARD_PUBLIC_KEY
logger = logging.getLogger(__name__)


class WireGuardManager:
    def __init__(self, wg_interface: str = "wg0", wg_config_path: str = "/etc/wireguard"):
        self.wg_interface = wg_interface
        self.wg_config_path = wg_config_path

    def generate_keypair(self) -> Tuple[str, str]:
        """Generate WireGuard private and public key pair"""
        try:
            # Generate private key
            private_key = subprocess.check_output(["sudo", "wg", "genkey"], text=True).strip()
            # Generate public key from private key
            public_key = subprocess.check_output(
                ["sudo", "wg", "pubkey"], input=private_key, text=True
            ).strip()
            return private_key, public_key
        except subprocess.CalledProcessError as e:
            logger.error(f"Error generating WireGuard keys: {e}")
            raise

    def generate_config_content(self, private_key: str, assigned_ip: str) -> str:
        """Generate WireGuard client configuration content"""
        config = f"""[Interface]
PrivateKey = {private_key}
Address = {assigned_ip}/32
DNS = 10.8.0.1

[Peer]
PublicKey = {WIREGUARD_PUBLIC_KEY}
Endpoint = {WIREGUARD_ENDPOINT}
AllowedIPs = 10.8.0.0/16
PersistentKeepalive = 25
"""
        return config

    def add_peer_to_server(self, public_key: str, allowed_ip: str) -> bool:
        """Add peer to WireGuard server configuration and persist it."""
        peer_config = f"""
[Peer]
PublicKey = {public_key}
AllowedIPs = {allowed_ip}/32
    """
        try:
            # Add the peer to the running wg interface (temporary)
            command = [
                "sudo", "wg", "set", self.wg_interface,
                "peer", public_key,
                "allowed-ips", f"{allowed_ip}/32"
            ]
            subprocess.run(command, check=True)
            logger.info(f"Added peer {public_key} with IP {allowed_ip}")

            # Append peer to the wg config file for persistence
            config_path = f"{self.wg_config_path}/{self.wg_interface}.conf"
            subprocess.run(["sudo", "tee", "-a", config_path], input=peer_config, text=True, check=True)
            logger.info(f"Persisted peer {public_key} to config file")

            return True
        except subprocess.CalledProcessError as e:
            logger.error(f"Error adding peer to server: {e}")
            return False
        except IOError as e:
            logger.error(f"Failed to write peer to config file: {e}")
            return False

    def remove_peer_from_server(self, public_key: str) -> bool:
        """Remove peer from WireGuard server configuration"""
        try:
            command = ["sudo", "wg", "set", self.wg_interface, "peer", public_key, "remove"]
            subprocess.run(command, check=True)
            logger.info(f"Removed peer {public_key}")
            return True
        except subprocess.CalledProcessError as e:
            logger.error(f"Error removing peer from server: {e}")
            return False
