from django import forms
from .models import Shift, Employee

class ShiftForm(forms.ModelForm):
    class Meta:
        model = Shift
        fields = ['employee', 'date', 'shift_type', 'start_time', 'end_time', 'notes']
        widgets = {
            'date': forms.DateInput(attrs={'type': 'date'}),
            'start_time': forms.TimeInput(attrs={'type': 'time'}),
            'end_time': forms.TimeInput(attrs={'type': 'time'}),
        }