from django import forms
from pathlib import Path


class DocumentUploadForm(forms.Form):
    id_document = forms.FileField(required=False, label='Valid ID (front)')
    id_document_back = forms.FileField(required=False, label='Valid ID (back)')
    selfie_document = forms.FileField(required=False, label='Selfie holding valid ID')
    resume_document = forms.FileField(required=False, label='Resume (PDF)')
    nbi_clearance = forms.FileField(required=False)
    police_clearance = forms.FileField(required=False)
    barangay_clearance = forms.FileField(required=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            field.widget.attrs['accept'] = '.pdf' if name == 'resume_document' else ('.jpg,.jpeg,.png' if name == 'selfie_document' else '.pdf,.jpg,.jpeg,.png')

    def clean(self):
        data = super().clean()
        if not any(data.values()):
            raise forms.ValidationError('Choose at least one document.')
        for name, upload in list(data.items()):
            if not upload:
                continue
            if upload.size > 5 * 1024 * 1024:
                self.add_error(name, 'Maximum file size is 5 MB.')
                continue
            header = upload.read(16)
            upload.seek(0)
            kind = ('application/pdf' if header.startswith(b'%PDF-') else
                    'image/png' if header.startswith(b'\x89PNG\r\n\x1a\n') else
                    'image/jpeg' if header.startswith(b'\xff\xd8\xff') else '')
            extensions = {'application/pdf': ('.pdf',), 'image/png': ('.png',), 'image/jpeg': ('.jpg', '.jpeg')}
            if (Path(upload.name).suffix.lower() not in extensions.get(kind, ())
                    or (name == 'resume_document' and kind != 'application/pdf')
                    or (name == 'selfie_document' and kind not in ('image/png', 'image/jpeg'))):
                self.add_error(name, 'Use a PDF, JPG or PNG with matching contents. Resumes must be PDF.')
            else:
                upload.content_type = kind
        return data
