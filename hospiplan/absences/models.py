from django.db import models


class AbsenceType(models.Model):
    name = models.CharField(max_length=100)
    impacts_quota = models.BooleanField()

    def __str__(self):
        return self.name


class Absence(models.Model):
    staff = models.ForeignKey(
        'staff.Staff', on_delete=models.CASCADE, related_name='absences'
    )
    absence_type = models.ForeignKey(AbsenceType, on_delete=models.CASCADE)
    start_date = models.DateField()
    expected_end_date = models.DateField()
    actual_end_date = models.DateField(null=True, blank=True)
    is_planned = models.BooleanField()

    def __str__(self):
        return f"{self.staff} - {self.absence_type} ({self.start_date})"
