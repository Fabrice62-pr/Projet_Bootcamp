from django.db import models


class Service(models.Model):
    name = models.CharField(max_length=100)
    manager = models.ForeignKey(
        'staff.Staff', null=True, blank=True, on_delete=models.SET_NULL, related_name='managed_services'
    )
    bed_capacity = models.IntegerField()
    criticality_level = models.IntegerField()
    # Seuil minimum de soignants qualifiés affectés (contrainte dure #4)
    min_staff_threshold = models.IntegerField(default=1)

    def __str__(self):
        return self.name


class CareUnit(models.Model):
    service = models.ForeignKey(Service, on_delete=models.CASCADE, related_name='care_units')
    name = models.CharField(max_length=100)

    def __str__(self):
        return f"{self.service} - {self.name}"


class ServiceStatus(models.Model):
    service = models.ForeignKey(Service, on_delete=models.CASCADE, related_name='statuses')
    status = models.CharField(max_length=50)
    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)

    def __str__(self):
        return f"{self.service} - {self.status}"


class StaffServiceAssignment(models.Model):
    staff = models.ForeignKey(
        'staff.Staff', on_delete=models.CASCADE, related_name='service_assignments'
    )
    service = models.ForeignKey(Service, on_delete=models.CASCADE, related_name='staff_assignments')
    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)

    def __str__(self):
        return f"{self.staff} -> {self.service}"
