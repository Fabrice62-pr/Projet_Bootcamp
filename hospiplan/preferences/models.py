from django.db import models


class Preference(models.Model):
    staff = models.ForeignKey(
        'staff.Staff', on_delete=models.CASCADE, related_name='preferences'
    )
    type = models.CharField(max_length=50)
    description = models.CharField(max_length=255)
    is_hard_constraint = models.BooleanField()
    start_date = models.DateField()
    end_date = models.DateField()

    def __str__(self):
        return f"{self.staff} - {self.type} ({'dur' if self.is_hard_constraint else 'souple'})"
