from django.db import migrations


def populate_basis_of_record(apps, schema_editor):
    BasisOfRecord = apps.get_model("dashboard", "BasisOfRecord")
    Observation = apps.get_model("dashboard", "Observation")

    # Get all distinct basis_of_record values
    distinct_values = (
        Observation.objects.exclude(basis_of_record="")
        .values_list("basis_of_record", flat=True)
        .distinct()
    )

    # Create BasisOfRecord entries and build lookup
    lookup = {}
    for value in distinct_values:
        bor, _ = BasisOfRecord.objects.get_or_create(name=value)
        lookup[value] = bor

    # Update observations in batches
    for text_value, bor_obj in lookup.items():
        Observation.objects.filter(basis_of_record=text_value).update(
            basis_of_record_fk=bor_obj
        )


def reverse_populate(apps, schema_editor):
    # No-op: the old TextField still has the data
    pass


class Migration(migrations.Migration):
    dependencies = [
        ("dashboard", "0022_add_basis_of_record_fk_and_m2m"),
    ]

    operations = [
        migrations.RunPython(populate_basis_of_record, reverse_populate),
    ]
