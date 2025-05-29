import requests
import json
from config import Config, setup_logger

# Get logger
logger = setup_logger('ROUTER.CONTROL')

class RouterControl:
    def __init__(self):
        self.config = Config()
        self.base_url = f"http://{self.config.config['router_ip']}/rest/ip/kid-control"
        self.auth = (self.config.config['username'], self.config.config['password'])
    
    def check_firewall_status(self):
        """Check if KidControl rule is disabled."""
        try:
            response = requests.get(self.base_url, auth=self.auth)
            response.raise_for_status()
            rules = response.json()
            
            for rule in rules:
                if rule['name'] == self.config.config['rule_name']:
                    if rule.get('disabled') == 'true':
                        network_status = "enabled"
                    else:
                        network_status = "disabled"

                    #logger.info(f"KidControl: Rule is: {network_status}, Rule is: {rule.get('disabled')}")

                    # Update status in config
                    self.config.set_network_status(network_status)
                    return network_status
            
            logger.error("Rule not found in router configuration")
            return None
        except Exception as e:
            logger.error(f"Error checking KidControl status: {str(e)}")
            return None
    
    def get_devices_under_max(self):
        """Get all devices under the maximum allowed time."""
        try:
            response = requests.get(f"{self.base_url}/device", auth=self.auth)
            response.raise_for_status()
            devices = response.json()
            # Update devices in data file
            device_list = []
            for device in devices:
                name = device.get('name')
                user = device.get('user', '').strip()
                disabled = device.get('disabled', False)
                
                if user and user == self.config.config['rule_name']:
                    device_list.append(f"{name}:{disabled}")
            
            # Update devices in JSON data
            self.config.set_devices(device_list)
            return True
            
        except Exception as e:
            logger.error(f"Error getting devices: {str(e)}")
            return False
    
    def update_devices_under_max(self):
        """Update the status of devices under the maximum allowed time."""
        try:
            # Read devices from JSON data
            devices = [(device.split(':')[0], device.split(':')[1]) 
                      for device in self.config.get_devices()]
            
            for device_name, device_status in devices:
                # Get device info from router
                response = requests.get(f"{self.base_url}/device", auth=self.auth)
                response.raise_for_status()
                devices_info = response.json()
                
                # Find the device
                device_info = next((d for d in devices_info if d.get('name') == device_name), None)
                if not device_info:
                    logger.error(f"Device not found on RouterOS: {device_name}")
                    continue
                
                # Get device ID
                device_id = device_info.get('.id') or device_info.get('id')
                if not device_id:
                    logger.error(f"Device ID not found for {device_name}")
                    continue
                
                # If the device is already disabled, don't update it
                if device_status == device_info.get('disabled'):
                    continue
                
                # Prepare updated device info
                device_info['disabled'] = device_status

                if 'blocked' in device_info:
                    del device_info['blocked']
                if 'ip-address' in device_info:
                    del device_info['ip-address']
                if 'idle-time' in device_info:
                    del device_info['idle-time']
                if 'bytes-down' in device_info:
                    del device_info['bytes-down']
                if 'bytes-up' in device_info:   
                    del device_info['bytes-up']
                if 'rate-down' in device_info:
                    del device_info['rate-down']
                if 'rate-up' in device_info:
                    del device_info['rate-up']
                if 'activity' in device_info:
                    del device_info['activity']
                if 'dynamic' in device_info:
                    del device_info['dynamic']
                if 'inactive' in device_info:
                    del device_info['inactive']
                if 'limited' in device_info:
                    del device_info['limited']
                if 'paused' in device_info:
                    del device_info['paused']

                #logger.info(f"Updating device: {device_name} ({device_info} ) with status: {device_status}")

                # Update device on router
                try:
                    response = requests.put(
                        f"{self.base_url}/device/{device_id}",
                        auth=self.auth,
                        json=device_info
                    )
                    response.raise_for_status()
                    logger.info(f"Successfully updated device: {device_name} => status: {device_status}")
                except Exception as e:
                    logger.error(f"Failed to update device {device_name}: {str(e)}")
                    logger.error(f"Request URL: {self.base_url}/device/{device_id}")
                    logger.error(f"Request data: {json.dumps(device_info)}")
                    continue
                
            return True
        except Exception as e:
            logger.error(f"Error updating devices: {str(e)}")
            return False
    
    def update_rule_status(self, disabled):
        """Update the status of the KidControl rule."""
        try:
            # Get current rules
            response = requests.get(self.base_url, auth=self.auth)
            response.raise_for_status()
            rules = response.json()
            
            # Find our rule
            rule = next((r for r in rules if r.get('name') == self.config.config['rule_name']), None)
            if not rule:
                logger.error("Rule not found in router configuration")
                return False

            # Get rule ID
            rule_id = rule.get('.id') or rule.get('id')
            if not rule_id:
                logger.error("Rule ID not found")
                return False
            

            # Prepare updated rule
            if disabled:
                rule['disabled'] = 'true'
            else:
                rule['disabled'] = 'false'
            
            if 'paused' in rule:
                del rule['paused']
            if 'blocked' in rule:
                del rule['blocked']
            

            # Update rule on router
            response = requests.put(
                f"{self.base_url}/{rule_id}",
                auth=self.auth,
                json=rule
            )

            response.raise_for_status()
            
            return True
        except Exception as e:
            logger.error(f"Error updating rule status: {str(e)}")
            return False 