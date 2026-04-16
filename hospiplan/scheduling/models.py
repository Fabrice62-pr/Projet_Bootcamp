from django.db import models


class ShiftType(models.Model):
    name = models.CharField(max_length=50)
    duration_hours = models.IntegerField()
    requires_rest_after = models.BooleanField(default=False)
    # Durée de repos réglementaire après cette garde (contrainte dure #3)
    rest_duration_hours = models.IntegerField(default=11)
    # Identifie explicitement les gardes de nuit (contrainte dure #5)
    is_night_shift = models.BooleanField(default=False)

    def __str__(self):
        return self.name


class Shift(models.Model):
    care_unit = models.ForeignKey(
        'services.CareUnit', on_delete=models.CASCADE, related_name='shifts'
    )
    shift_type = models.ForeignKey(ShiftType, on_delete=models.CASCADE, related_name='shifts')
    start_datetime = models.DateTimeField()
    end_datetime = models.DateTimeField()
    min_staff = models.IntegerField()
    max_staff = models.IntegerField()

    def __str__(self):
        return f"{self.shift_type} | {self.care_unit} | {self.start_datetime:%Y-%m-%d %H:%M}"


class ShiftRequiredCertification(models.Model):
    shift = models.ForeignKey(Shift, on_delete=models.CASCADE, related_name='required_certifications')
    certification = models.ForeignKey(
        'staff.Certification', on_delete=models.CASCADE
    )

    class Meta:
        unique_together = ('shift', 'certification')


class ShiftAssignment(models.Model):
    shift = models.ForeignKey(Shift, on_delete=models.CASCADE, related_name='assignments')
    staff = models.ForeignKey(
        'staff.Staff', on_delete=models.CASCADE, related_name='shift_assignments'
    )
    assigned_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.staff} -> {self.shift}"
