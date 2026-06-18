from django.contrib import admin
from django import forms
from django.shortcuts import render, redirect
from django.contrib import messages
from .models import GlobalShiftTemplate, Department, ShiftTemplate

class ApplyTemplateForm(forms.Form):
    template = forms.ModelChoiceField(
        queryset=GlobalShiftTemplate.objects.filter(is_active=True),
        label='Επίλεξε Template'
    )
    departments = forms.ModelMultipleChoiceField(
        queryset=Department.objects.all(),
        widget=forms.CheckboxSelectMultiple,
        label='Επίλεξε Τμήματα'
    )

def apply_global_template(request):
    if request.method == 'POST':
        form = ApplyTemplateForm(request.POST)
        if form.is_valid():
            template = form.cleaned_data['template']
            departments = form.cleaned_data['departments']
            
            created = 0
            for dept in departments:
                ShiftTemplate.objects.get_or_create(
                    department=dept,
                    name=template.name,
                    defaults={
                        'start_time': template.start_time,
                        'end_time': template.end_time,
                        'is_active': True
                    }
                )
                created += 1
            
            messages.success(request, f'✅ Το template "{template.name}" εφαρμόστηκε σε {created} τμήματα!')
            return redirect('/admin/staff/shifttemplate/')
    else:
        form = ApplyTemplateForm()
    
    return render(request, 'staff/admin/apply_template.html', {
        'form': form,
        'title': 'Εφαρμογή Template σε Πολλά Τμήματα'
    })
