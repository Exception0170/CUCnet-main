# dns.py
import logging
from config import DNS_HOSTS
from shared.models import DNSRecord, Profile

logger = logging.getLogger(__name__)


class DNSManager:
    def __init__(self, database_manager):
        self.db = database_manager
        self.hosts_file = DNS_HOSTS

    def update_dnsmasq_hosts(self):
        """Update dnsmasq hosts file with active DNS records only"""
        try:
            # Get all active DNS records with user IPs
            session = self.db.get_session()
            active_records = []

            # Get all active DNS records and join with profiles to get IPs
            records = session.query(DNSRecord).filter_by(status='active').all()
            for record in records:
                # Get user's profiles to find assigned IPs
                profiles = session.query(Profile).filter_by(user_id=record.user_id).all()
                for profile in profiles:
                    active_records.append({
                        'ip': profile.assigned_ip,
                        'domain': record.domain
                    })

            session.close()

            # Generate hosts file content
            content = ""
            for record in active_records:
                content += f"{record['ip']}\t{record['domain']}\n"

            # Write to hosts file
            with open(self.hosts_file, 'w') as f:
                f.write(content)

            logger.info(f"Updated DNS hosts file with {len(active_records)} active records")
            return True

        except Exception as e:
            logger.error(f"Error updating DNS hosts: {e}")
            return False
