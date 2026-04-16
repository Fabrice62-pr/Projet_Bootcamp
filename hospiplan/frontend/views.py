from django.shortcuts import render


def dashboard(request):
    return render(request, 'frontend/dashboard.html')


# ── Soignants ──────────────────────────────────────────────────────────

def staff_list(request):
    return render(request, 'frontend/staff/list.html')


def staff_add(request):
    return render(request, 'frontend/staff/form.html')


def staff_edit(request, pk):
    return render(request, 'frontend/staff/form.html', {'staff_id': pk})


# ── Postes / Gardes ────────────────────────────────────────────────────

def shift_list(request):
    return render(request, 'frontend/shifts/list.html')


def shift_add(request):
    return render(request, 'frontend/shifts/form.html')


def shift_edit(request, pk):
    return render(request, 'frontend/shifts/form.html', {'shift_id': pk})


# ── Affectation ────────────────────────────────────────────────────────

def assignment_new(request):
    return render(request, 'frontend/assignments/form.html')


# ── Planning ───────────────────────────────────────────────────────────

def planning(request):
    return render(request, 'frontend/planning/planning.html')


# ── Référentiels ────────────────────────────────────────────────────────

def ref_services(request):
    return render(request, 'frontend/referentiel/services.html')


def ref_shift_types(request):
    return render(request, 'frontend/referentiel/shift_types.html')


def ref_contract_types(request):
    return render(request, 'frontend/referentiel/contract_types.html')
