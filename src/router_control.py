import requests
import json
from config import Config, setup_logger

# Get logger
logger = setup_logger('ROUTER.CONTROL')

class RouterControl:
    def __init__(self):
        self.config = Config()
        self.openwrt_ip = self.config.config.get('openwrt_ip')
        self.openwrt_user = self.config.config.get('openwrt_user')
        self.openwrt_password = self.config.config.get('password')

    def check_firewall_status(self):
        """Check restrict status by running check_restrict_status.sh on OpenWRT via SSH."""
        openwrt_ip = self.openwrt_ip
        openwrt_user = self.openwrt_user
        openwrt_password = self.openwrt_password

        try:
            ssh_cmd = f"sshpass -p '{openwrt_password}' ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null {openwrt_user}@{openwrt_ip} '/etc/config/scripts/check_restrict_status.sh'"
            import subprocess
            result = subprocess.run(ssh_cmd, shell=True, capture_output=True, text=True)
            if result.returncode == 0:
                network_status = "enabled"
                logger.info(f"check_restrict_status.sh executed on OpenWRT: {result.stdout}")
            elif result.returncode == 1:
                network_status = "disabled"
                logger.info(f"check_restrict_status.sh executed on OpenWRT: {result.stdout}")
            else:
                logger.error(f"check_restrict_status.sh returned unexpected code: {result.returncode}, stderr: {result.stderr}")
                return None
            self.config.set_network_status(network_status)
            return network_status
        except Exception as e:
            logger.error(f"Error checking restrict status via OpenWRT SSH: {str(e)}")
            return None
  
    def update_rule_status(self, disabled):
        """Update the status of the KidControl rule by calling a shell script on OpenWRT via SSH."""
        openwrt_ip = self.openwrt_ip
        openwrt_user = self.openwrt_user
        openwrt_password = self.openwrt_password

        action = 'on' if not disabled else 'off'
        try:
            ssh_cmd = f"sshpass -p '{openwrt_password}' ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null {openwrt_user}@{openwrt_ip} '/etc/config/scripts/toggle_restrict.sh {action}'"
            import subprocess
            result = subprocess.run(ssh_cmd, shell=True, capture_output=True, text=True)
            if result.returncode != 0:
                logger.error(f"Failed to run toggle_restrict.sh {action} on OpenWRT: {result.stderr}")
                return False
            logger.info(f"toggle_restrict.sh {action} executed on OpenWRT: {result.stdout}")
            # Optionally, reconnect devices if needed
            self.reconnect_all_devices()
            return True
        except Exception as e:
            logger.error(f"Error updating rule status via OpenWRT SSH: {str(e)}")
            return False
    
    def reconnect_all_devices(self):
        """Reconnect all devices by calling /root/reconnect.sh all on OpenWRT via SSH in a background thread."""
        openwrt_ip = self.openwrt_ip
        openwrt_user = self.openwrt_user
        openwrt_password = self.openwrt_password

        def run_disconnect():
            disconnect_cmd = '/etc/config/scripts/reconnect.sh all'
            ssh_cmd = (
                f"sshpass -p '{openwrt_password}' ssh -o StrictHostKeyChecking=no "
                f"-o UserKnownHostsFile=/dev/null {openwrt_user}@{openwrt_ip} '{disconnect_cmd}'"
            )
            import subprocess
            try:
                result = subprocess.run(ssh_cmd, shell=True, capture_output=True, text=True)
                if result.returncode == 0:
                    logger.info(f"reconnect.sh all executed successfully: {result.stdout}")
                else:
                    logger.error(f"reconnect.sh all failed: {result.stderr}")
            except Exception as e:
                logger.error(f"Error running reconnect.sh all: {str(e)}")

        import threading
        threading.Thread(target=run_disconnect, daemon=True).start()

