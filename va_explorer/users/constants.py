FEEDBACK_MODULE_CHOICES = (
    ("data_management", "Data Management"),
    ("personnel_management", "Personnel Management"),
    ("schedule_management", "Schedule Management"),
    ("analytics", "Dashboards (Analytics)"),
)

FEEDBACK_MODULE_FEATURES = {
    "data_management": [
        ("households", "Households"),
        ("pregnancies", "Pregnancies"),
        ("pregnancy_outcomes", "Pregnancy Outcomes"),
        ("deaths", "Deaths"),
        ("verbal_autopsies", "Verbal Autopsies"),
        ("data_cleanup", "Data Cleanup"),
        ("data_export", "Data Export"),
    ],
    "personnel_management": [
        ("users", "Users"),
        ("supervision", "Supervision"),
    ],
    "schedule_management": [
        ("scheduled_vas", "Scheduled Verbal Autopsies"),
    ],
    "analytics": [
        ("dashboards", "Analytics Dashboard"),
    ],
}
