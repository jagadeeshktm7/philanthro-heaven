from django import forms
from .models import NGOProfile, HelpRequest
from .cities import CATEGORIES

class NGOProfileForm(forms.ModelForm):
    # Causes as multiple checkboxes
    causes_choices = forms.MultipleChoiceField(
        choices=CATEGORIES,
        widget=forms.CheckboxSelectMultiple,
        label="Causes Supported",
        required=True
    )

    class Meta:
        model = NGOProfile
        fields = ('ngo_name', 'registration_number', 'description', 'city')
        widgets = {
            'description': forms.Textarea(attrs={'rows': 4}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Make registration number explicitly required
        self.fields['registration_number'].required = True
        
        # If instance exists, prepopulate causes_choices from the comma-separated string
        if self.instance and self.instance.pk and self.instance.causes:
            self.initial['causes_choices'] = [c.strip() for c in self.instance.causes.split(',')]

    def save(self, commit=True):
        profile = super().save(commit=False)
        # Join selected choices into a comma-separated string
        chosen_causes = self.cleaned_data.get('causes_choices', [])
        profile.causes = ','.join(chosen_causes)
        if commit:
            profile.save()
        return profile


class HelpRequestForm(forms.ModelForm):
    class Meta:
        model = HelpRequest
        fields = ('title', 'category', 'description', 'city', 'urgency')
        widgets = {
            'description': forms.Textarea(attrs={'rows': 4}),
        }
