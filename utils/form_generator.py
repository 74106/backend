from typing import Dict, Any, List
import json
from datetime import datetime

class LegalFormGenerator:
    """Advanced legal form generator with multiple form types"""
    
    def __init__(self):
        self.form_templates = {
            'FIR': {
                'title': 'First Information Report',
                'sections': [
                    'complainant_details',
                    'incident_details',
                    'accused_details',
                    'witness_details',
                    'evidence_details'
                ]
            },
            'RTI': {
                'title': 'Right to Information Application',
                'sections': [
                    'applicant_details',
                    'information_requested',
                    'public_authority',
                    'grounds_for_request'
                ]
            },
            'COMPLAINT': {
                'title': 'General Complaint Form',
                'sections': [
                    'complainant_details',
                    'complaint_details',
                    'relief_sought',
                    'supporting_documents'
                ]
            },
            'APPEAL': {
                'title': 'Legal Appeal Application',
                'sections': [
                    'appellant_details',
                    'original_order_details',
                    'grounds_for_appeal',
                    'relief_sought'
                ]
            }
        }
        
        self.section_templates = {
            'complainant_details': {
                'name': 'Full Name',
                'address': 'Complete Address',
                'phone': 'Phone Number',
                'email': 'Email Address',
                'id_proof': 'ID Proof Type and Number'
            },
            'incident_details': {
                'date_time': 'Date and Time of Incident',
                'location': 'Location of Incident',
                'description': 'Detailed Description of Incident',
                'loss_damage': 'Loss or Damage Suffered'
            },
            'accused_details': {
                'name': 'Name of Accused',
                'address': 'Address of Accused',
                'description': 'Description of Accused'
            },
            'witness_details': {
                'witness_names': 'Names of Witnesses',
                'witness_addresses': 'Addresses of Witnesses',
                'witness_phones': 'Phone Numbers of Witnesses'
            },
            'evidence_details': {
                'documents': 'Supporting Documents',
                'physical_evidence': 'Physical Evidence',
                'digital_evidence': 'Digital Evidence'
            },
            'applicant_details': {
                'name': 'Full Name',
                'address': 'Complete Address',
                'phone': 'Phone Number',
                'email': 'Email Address',
                'citizenship': 'Citizenship'
            },
            'information_requested': {
                'subject': 'Subject of Information',
                'details': 'Detailed Description of Information Required',
                'period': 'Time Period for Information',
                'format': 'Preferred Format of Information'
            },
            'public_authority': {
                'authority_name': 'Name of Public Authority',
                'officer_name': 'Name of Public Information Officer',
                'address': 'Address of Public Authority'
            },
            'grounds_for_request': {
                'reason': 'Reason for Requesting Information',
                'public_interest': 'Public Interest Justification'
            },
            'complaint_details': {
                'subject': 'Subject of Complaint',
                'description': 'Detailed Description of Complaint',
                'date_occurred': 'Date When Issue Occurred',
                'previous_actions': 'Previous Actions Taken'
            },
            'relief_sought': {
                'compensation': 'Compensation Sought',
                'action_required': 'Action Required from Authority',
                'timeframe': 'Expected Timeframe for Resolution'
            },
            'supporting_documents': {
                'documents': 'List of Supporting Documents',
                'photographs': 'Photographs (if any)',
                'correspondence': 'Previous Correspondence'
            },
            'appellant_details': {
                'name': 'Full Name of Appellant',
                'address': 'Complete Address',
                'phone': 'Phone Number',
                'email': 'Email Address',
                'representative': 'Legal Representative (if any)'
            },
            'original_order_details': {
                'order_number': 'Original Order Number',
                'order_date': 'Date of Original Order',
                'issuing_authority': 'Authority that Issued Order',
                'order_summary': 'Summary of Original Order'
            },
            'grounds_for_appeal': {
                'legal_grounds': 'Legal Grounds for Appeal',
                'errors': 'Errors in Original Order',
                'new_evidence': 'New Evidence Available'
            }
        }
        
        # Simple, concrete examples to guide users with low literacy.
        # Keys mirror section_templates field keys for easy lookup.
        self.field_examples = {
            'name': 'e.g., Ramesh Kumar',
            'address': 'e.g., House No. 12, Ward 4, Jaipur, Rajasthan',
            'phone': 'e.g., 9876543210',
            'email': 'e.g., yourname@example.com',
            'id_proof': 'e.g., Aadhaar 1234-5678-9012',
            'date_time': 'e.g., 15 Aug 2025, 8:30 PM',
            'location': 'e.g., Near Bus Stand, Alwar',
            'description': 'e.g., Briefly describe what happened in simple words',
            'loss_damage': 'e.g., Broken phone, injury to hand',
            'witness_names': 'e.g., Sita Devi, Mohan Lal',
            'witness_addresses': 'e.g., Village Rampur, Tehsil Kotputli',
            'witness_phones': 'e.g., 9812345678, 9801234567',
            'documents': 'e.g., Bills, photos, FIR copy',
            'physical_evidence': 'e.g., Damaged item, clothes',
            'digital_evidence': 'e.g., WhatsApp chats, call recordings',
            'citizenship': 'e.g., Indian',
            'subject': 'e.g., Information about village road repair',
            'details': 'e.g., Copy of tender and progress reports',
            'period': 'e.g., Jan 2023 to Dec 2023',
            'format': 'e.g., Photocopy or PDF via email',
            'authority_name': 'e.g., Public Works Department, Jaipur',
            'officer_name': 'e.g., PIO Mr. Sharma',
            'reason': 'e.g., To ensure proper use of public money',
            'public_interest': 'e.g., Road is unsafe for villagers',
            'complaint_details': 'e.g., Shopkeeper overcharged for items',
            'date_occurred': 'e.g., 10 July 2025',
            'previous_actions': 'e.g., Spoke to manager on 12 July 2025',
            'compensation': 'e.g., Refund of Rs. 1500',
            'action_required': 'e.g., Inspect shop and take action',
            'timeframe': 'e.g., Within 15 days',
            'photographs': 'e.g., Photo of the damaged road',
            'correspondence': 'e.g., Previous emails/letters to authority',
            'representative': 'e.g., Advocate Meena (optional)',
            'order_number': 'e.g., Order No. 123/2025',
            'order_date': 'e.g., 05 June 2025',
            'issuing_authority': 'e.g., SDM, Jaipur',
            'order_summary': 'e.g., Brief summary of the original order',
            'legal_grounds': 'e.g., Section 420 IPC not considered',
            'errors': 'e.g., Evidence was ignored',
            'new_evidence': 'e.g., New witness statement dated 01 Aug 2025'
        }
    
    def generate_form(self, form_type: str, responses: Dict[str, Any]) -> str:
        """Generate a comprehensive legal form"""
        if form_type not in self.form_templates:
            return f"Error: Unknown form type '{form_type}'"
        
        template = self.form_templates[form_type]
        form_content = []
        
        # Add header
        form_content.append("=" * 80)
        form_content.append(f"{template['title'].center(80)}")
        form_content.append("=" * 80)
        form_content.append(f"Generated on: {datetime.now().strftime('%B %d, %Y at %I:%M %p')}")
        form_content.append("")
        
        # Generate sections
        for section in template['sections']:
            if section in self.section_templates:
                form_content.extend(self._generate_section(section, responses))
        
        # Add footer
        form_content.append("")
        form_content.append("=" * 80)
        form_content.append("IMPORTANT NOTES:")
        form_content.append("• This is a computer-generated form for reference purposes")
        form_content.append("• Please verify all information before submission")
        form_content.append("• Consult with a legal professional for final review")
        form_content.append("• Keep copies of all supporting documents")
        form_content.append("=" * 80)
        
        return "\n".join(form_content)
    
    def _generate_section(self, section_name: str, responses: Dict[str, Any]) -> List[str]:
        """Generate content for a specific section"""
        section_content = []
        section_template = self.section_templates[section_name]
        
        # Section header
        section_title = section_name.replace('_', ' ').title()
        section_content.append(f"--- {section_title} ---")
        section_content.append("")
        
        # Generate fields
        for field_key, field_label in section_template.items():
            field_value = responses.get(field_key, '')
            
            if field_value:
                section_content.append(f"{field_label}: {field_value}")
            else:
                example_hint = self.field_examples.get(field_key)
                if example_hint:
                    section_content.append(f"{field_label}: _________________ ({example_hint})")
                else:
                    section_content.append(f"{field_label}: _________________")
            
            section_content.append("")
        
        return section_content
    
    def get_form_fields(self, form_type: str) -> Dict[str, List[str]]:
        """Get available fields for a specific form type"""
        if form_type not in self.form_templates:
            return {}
        
        fields = {}
        for section in self.form_templates[form_type]['sections']:
            if section in self.section_templates:
                fields[section] = list(self.section_templates[section].keys())
        
        return fields

# Global instance
form_generator = LegalFormGenerator()

def generate_form(form_type: str, responses: Dict[str, Any]) -> str:
    """Main function to generate legal forms"""
    try:
        return form_generator.generate_form(form_type, responses)
    except Exception as e:
        return f"Error generating form: {str(e)}"

def get_form_fields(form_type: str) -> Dict[str, List[str]]:
    """Get available fields for a form type"""
    try:
        return form_generator.get_form_fields(form_type)
    except Exception as e:
        return {}

def get_field_examples(form_type: str) -> Dict[str, Dict[str, str]]:
    """Return example hints for each field grouped by section for a given form type."""
    try:
        if form_type not in form_generator.form_templates:
            return {}
        result: Dict[str, Dict[str, str]] = {}
        for section in form_generator.form_templates[form_type]['sections']:
            section_fields = form_generator.section_templates.get(section, {})
            examples_for_section: Dict[str, str] = {}
            for field_key in section_fields.keys():
                example = form_generator.field_examples.get(field_key, '')
                if example:
                    examples_for_section[field_key] = example
            if examples_for_section:
                result[section] = examples_for_section
        return result
    except Exception:
        return {}
