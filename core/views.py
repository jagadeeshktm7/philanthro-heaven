from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .models import NGOProfile, HelpRequest, Match
from .forms import NGOProfileForm, HelpRequestForm
from .ai_engine import calculate_priority, check_duplicate, check_suspicious, get_top_matches, match_score, haversine_km

# Helper function to redirect user to their proper dashboard
def redirect_user_dashboard(user):
    if user.role == 'donor':
        return redirect('donor_dashboard')
    elif user.role == 'ngo':
        return redirect('ngo_dashboard')
    elif user.role == 'beneficiary':
        return redirect('beneficiary_dashboard')
    return redirect('home')

# NGO Profile create or edit view
@login_required
def ngo_profile_view(request):
    # Check if user is NGO
    if request.user.role != 'ngo':
        messages.error(request, 'Access denied. Redirected to your correct dashboard.')
        return redirect_user_dashboard(request.user)

    # Get existing profile or None if not created yet
    profile = NGOProfile.objects.filter(user=request.user).first()

    if request.method == 'POST':
        if profile:
            form = NGOProfileForm(request.POST, instance=profile)
        else:
            form = NGOProfileForm(request.POST)
            
        if form.is_valid():
            ngo_profile = form.save(commit=False)
            ngo_profile.user = request.user
            ngo_profile.save()
            messages.success(request, 'NGO profile saved successfully!')
            return redirect('ngo_dashboard')
    else:
        if profile:
            form = NGOProfileForm(instance=profile)
        else:
            form = NGOProfileForm()

    return render(request, 'core/ngo_profile.html', {'form': form, 'profile': profile})

# Beneficiary new help request view
@login_required
def new_help_request_view(request):
    if request.user.role != 'beneficiary':
        messages.error(request, 'Access denied. Redirected to your correct dashboard.')
        return redirect_user_dashboard(request.user)

    if request.method == 'POST':
        form = HelpRequestForm(request.POST)
        if form.is_valid():
            help_req = form.save(commit=False)
            help_req.beneficiary = request.user
            
            # Run AI Engine calculations
            score, label = calculate_priority(help_req.title, help_req.description, help_req.category, help_req.urgency)
            help_req.priority = score
            help_req.priority_label = label
            
            # Save first so it can be queried for duplicate / suspicious checks
            help_req.save()
            
            help_req.is_duplicate = check_duplicate(help_req)
            help_req.is_suspicious = check_suspicious(help_req)
            help_req.save()

            # Create Match rows for top 3 NGOs
            top_ngos = get_top_matches(help_req, how_many=3)
            for rank, (ngo, m_score) in enumerate(top_ngos, start=1):
                Match.objects.create(
                    request=help_req,
                    ngo=ngo,
                    score=m_score,
                    rank=rank
                )

            # Show success message with priority label or duplicate warning
            if help_req.is_duplicate:
                messages.warning(request, f'Help request saved, but flagged as a duplicate. Priority: {label}')
            else:
                messages.success(request, f'Help request submitted successfully! Priority: {label}')
                
            return redirect('beneficiary_requests')
    else:
        form = HelpRequestForm()

    return render(request, 'core/new_help_request.html', {'form': form})

# Beneficiary list of requests view
@login_required
def beneficiary_requests_view(request):
    if request.user.role != 'beneficiary':
        messages.error(request, 'Access denied. Redirected to your correct dashboard.')
        return redirect_user_dashboard(request.user)

    requests_list = HelpRequest.objects.filter(beneficiary=request.user).order_by('-created_at')
    
    # Attach top matched NGOs names for each request
    request_data = []
    for req in requests_list:
        matches = Match.objects.filter(request=req).order_by('rank')[:3]
        top_ngo_names = [m.ngo.ngo_name for m in matches]
        request_data.append({
            'request': req,
            'top_ngo_names': top_ngo_names
        })

    return render(request, 'core/beneficiary_requests.html', {'request_data': request_data})

# NGO open requests list view (verified check required)
@login_required
def ngo_open_requests_view(request):
    if request.user.role != 'ngo':
        messages.error(request, 'Access denied. Redirected to your correct dashboard.')
        return redirect_user_dashboard(request.user)

    # Check if NGO profile exists and is verified
    profile = NGOProfile.objects.filter(user=request.user).first()
    if not profile or not profile.is_verified:
        return render(request, 'core/ngo_not_verified.html')

    # Show pending requests that are not duplicates
    open_requests = HelpRequest.objects.filter(status='pending', is_duplicate=False).order_by('-created_at')
    
    # For each request, calculate match score, distance, and top 3 recommended check
    request_items = []
    for req in open_requests:
        m_score = match_score(req, profile)
        score_percent = int(m_score * 100)
        distance = round(haversine_km(req.latitude, req.longitude, profile.latitude, profile.longitude), 1)
        
        # Check if this NGO is in the top 3 matches for this request
        top_matches = Match.objects.filter(request=req).order_by('rank')[:3]
        is_recommended = any(m.ngo == profile for m in top_matches)
        
        request_items.append({
            'request': req,
            'score_percent': score_percent,
            'distance': distance,
            'is_recommended': is_recommended
        })

    # Sort request items by match score high to low
    request_items.sort(key=lambda x: x['score_percent'], reverse=True)

    return render(request, 'core/ngo_open_requests.html', {'request_items': request_items})

# NGO accept request action view (requires POST)
@login_required
def ngo_accept_request_view(request, request_id):
    if request.user.role != 'ngo':
        messages.error(request, 'Access denied.')
        return redirect_user_dashboard(request.user)

    if request.method != 'POST':
        return redirect('ngo_open_requests')

    profile = NGOProfile.objects.filter(user=request.user).first()
    if not profile or not profile.is_verified:
        messages.error(request, 'Your NGO must be verified by admin to accept requests.')
        return redirect('ngo_open_requests')

    help_req = get_object_or_404(HelpRequest, id=request_id, status='pending')
    help_req.status = 'accepted'
    help_req.accepted_by = profile
    help_req.save()
    messages.success(request, 'Help request accepted successfully!')
    return redirect('ngo_open_requests')

# NGO accepted requests list view
@login_required
def ngo_accepted_requests_view(request):
    if request.user.role != 'ngo':
        messages.error(request, 'Access denied. Redirected to your correct dashboard.')
        return redirect_user_dashboard(request.user)

    profile = NGOProfile.objects.filter(user=request.user).first()
    if not profile or not profile.is_verified:
        return render(request, 'core/ngo_not_verified.html')

    accepted_requests = HelpRequest.objects.filter(accepted_by=profile, status='accepted').order_by('-created_at')
    return render(request, 'core/ngo_accepted_requests.html', {'accepted_requests': accepted_requests})

# NGO mark request completed action view (requires POST)
@login_required
def ngo_complete_request_view(request, request_id):
    if request.user.role != 'ngo':
        messages.error(request, 'Access denied.')
        return redirect_user_dashboard(request.user)

    if request.method != 'POST':
        return redirect('ngo_accepted_requests')

    profile = NGOProfile.objects.filter(user=request.user).first()
    if not profile or not profile.is_verified:
        messages.error(request, 'Your NGO must be verified.')
        return redirect('ngo_accepted_requests')

    help_req = get_object_or_404(HelpRequest, id=request_id, accepted_by=profile, status='accepted')
    help_req.status = 'completed'
    help_req.save()
    messages.success(request, 'Help request marked as completed!')
    return redirect('ngo_accepted_requests')
