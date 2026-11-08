from django.db import models


class Staff(models.Model):
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    email = models.EmailField(unique=True)
    phone = models.CharField(max_length=20)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.first_name} {self.last_name}"


class Role(models.Model):
    name = models.CharField(max_length=100)

    def __str__(self):
        return self.name


class StaffRole(models.Model):
    staff = models.ForeignKey(Staff, on_delete=models.CASCADE, related_name='staff_roles')
    role = models.ForeignKey(Role, on_delete=models.CASCADE)

    class Meta:
        unique_together = ('staff', 'role')


class Specialty(models.Model):
    name = models.CharField(max_length=100)
    parent = models.ForeignKey(
        'self', null=True, blank=True, on_delete=models.CASCADE, related_name='children'
    )

    def __str__(self):
        return self.name


class StaffSpecialty(models.Model):
    staff = models.ForeignKey(Staff, on_delete=models.CASCADE, related_name='staff_specialties')
    specialty = models.ForeignKey(Specialty, on_delete=models.CASCADE)

    class Meta:
        unique_together = ('staff', 'specialty')


class ContractType(models.Model):
    name = models.CharField(max_length=100)
    max_hours_per_week = models.IntegerField()
    leave_days_per_year = models.IntegerField()
    night_shift_allowed = models.BooleanField()
    max_consecutive_nights = models.IntegerField(default=3)

    def __str__(self):
        return self.name


class Contract(models.Model):
    staff = models.ForeignKey(Staff, on_delete=models.CASCADE, related_name='contracts')
    contract_type = models.ForeignKey(ContractType, on_delete=models.CASCADE)
    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)
    workload_percent = models.IntegerField()

    def __str__(self):
        return f"{self.staff} - {self.contract_type}"


class Certification(models.Model):
    name = models.CharField(max_length=100)

    def __str__(self):
        return self.name


class CertificationDependency(models.Model):
    parent_cert = models.ForeignKey(
        Certification, related_name='parent_dependencies', on_delete=models.CASCADE
    )
    required_cert = models.ForeignKey(
        Certification, related_name='required_dependencies', on_delete=models.CASCADE
    )

    class Meta:
        unique_together = ('parent_cert', 'required_cert')


class StaffCertification(models.Model):
    staff = models.ForeignKey(Staff, on_delete=models.CASCADE, related_name='certifications')
    certification = models.ForeignKey(Certification, on_delete=models.CASCADE)
    obtained_date = models.DateField()
    expiration_date = models.DateField()

    def __str__(self):
        return f"{self.staff} - {self.certification}"
