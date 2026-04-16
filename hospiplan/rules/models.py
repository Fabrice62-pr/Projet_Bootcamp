from django.db import models


class Rule(models.Model):
    name = models.CharField(max_length=100)
    description = models.TextField()
    rule_type = models.CharField(max_length=50)
    value = models.FloatField()
    unit = models.CharField(max_length=50)
    valid_from = models.DateField()
    valid_to = models.DateField(null=True, blank=True)

    def __str__(self):
        return self.name


class PatientLoad(models.Model):
    care_unit = models.ForeignKey(
        'services.CareUnit', on_delete=models.CASCADE, related_name='patient_loads'
    )
    date = models.DateField()
    patient_count = models.IntegerField()
    occupancy_rate = models.FloatField()

    def __str__(self):
        return f"{self.care_unit} - {self.date}"


class StaffLoan(models.Model):
    staff = models.ForeignKey(
        'staff.Staff', on_delete=models.CASCADE, related_name='loans'
    )
    from_service = models.ForeignKey(
        'services.Service', related_name='loans_from', on_delete=models.CASCADE
    )
    to_service = models.ForeignKey(
        'services.Service', related_name='loans_to', on_delete=models.CASCADE
    )
    start_date = models.DateField()
    end_date = models.DateField()

    def __str__(self):
        return f"{self.staff} : {self.from_service} -> {self.to_service}"
