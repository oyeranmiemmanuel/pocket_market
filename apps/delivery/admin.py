from django.contrib import admin

from .models import Delivery, DeliveryUpdate
from .services import advance_stage


class DeliveryUpdateInline(admin.TabularInline):
    model = DeliveryUpdate
    extra = 0
    readonly_fields = ["stage", "note", "created_at"]
    can_delete = False
    ordering = ["created_at"]


@admin.register(Delivery)
class DeliveryAdmin(admin.ModelAdmin):
    list_display = ["order", "method", "current_stage", "estimated_delivery_date"]
    list_filter = ["method", "current_stage"]
    search_fields = ["order__reference", "tracking_number", "courier_name"]
    inlines = [DeliveryUpdateInline]
    readonly_fields = ["order", "method"]

    def save_model(self, request, obj, form, change):
        """
        Route stage changes through advance_stage() so they're validated
        against this delivery's method and logged as a DeliveryUpdate -
        editing current_stage directly in the admin form still goes
        through the same rules a code-driven update would.
        """
        if change and "current_stage" in form.changed_data:
            advance_stage(obj, obj.current_stage, note="Updated via admin.")
            # advance_stage already saved current_stage; let the rest of
            # the form's fields (tracking_number, courier_name, etc) save
            # normally without re-touching current_stage.
            obj.refresh_from_db()
            for field in form.changed_data:
                if field != "current_stage":
                    setattr(obj, field, form.cleaned_data[field])
            obj.save()
        else:
            super().save_model(request, obj, form, change)
