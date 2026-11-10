from django.conf import settings
from django.db import models
from .cities import CITIES, CATEGORIES

class NGOProfile(models.Model):
    # Link to custom user model
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    ngo_name = models.CharField(max_length=200)
    registration_number = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    causes = models.CharField(max_length=255, help_text="Comma-separated categories")
    city = models.CharField(max_length=100, choices=[(c, c) for c in CITIES.keys()])
    latitude = models.FloatField(null=True, blank=True)
    longitude = models.FloatField(null=True, blank=True)
    is_verified = models.BooleanField(default=False)
    rating = models.FloatField(default=3.0)

    def save(self, *args, **kwargs):
        # Automatically fill latitude and longitude from the selected city
        if self.city in CITIES:
            lat, lon = CITIES[self.city]
            self.latitude = lat
            self.longitude = lon
        super().save(*args, **kwargs)

    def __str__(self):
        return self.ngo_name


class HelpRequest(models.Model):
    # Urgency choices
    URGENCY_CHOICES = [
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
    ]

    # Status choices
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('accepted', 'Accepted'),
        ('completed', 'Completed'),
        ('rejected', 'Rejected'),
    ]

    beneficiary = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    title = models.CharField(max_length=200)
    category = models.CharField(max_length=100, choices=CATEGORIES)
    description = models.TextField()
    city = models.CharField(max_length=100, choices=[(c, c) for c in CITIES.keys()])
    latitude = models.FloatField(null=True, blank=True)
    longitude = models.FloatField(null=True, blank=True)
    urgency = models.CharField(max_length=20, choices=URGENCY_CHOICES, default='medium')
    priority = models.FloatField(null=True, blank=True) # Filled by AI
    priority_label = models.CharField(max_length=50, blank=True) # Filled by AI: Critical, High, Normal
    is_suspicious = models.BooleanField(default=False) # Filled by AI
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    accepted_by = models.ForeignKey(NGOProfile, on_delete=models.SET_NULL, null=True, blank=True)
    is_duplicate = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        # Automatically fill latitude and longitude from the selected city
        if self.city in CITIES:
            lat, lon = CITIES[self.city]
            self.latitude = lat
            self.longitude = lon
        super().save(*args, **kwargs)

    def __str__(self):
        return self.title


class Match(models.Model):
    request = models.ForeignKey(HelpRequest, on_delete=models.CASCADE)
    ngo = models.ForeignKey(NGOProfile, on_delete=models.CASCADE)
    score = models.FloatField()
    rank = models.IntegerField()

    def __str__(self):
        return f"{self.request.title} -> {self.ngo.ngo_name} ({self.score})"
