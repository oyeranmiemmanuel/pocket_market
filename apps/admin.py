# from django.contrib import admin
# from .models import Product, Order, ContactMessage


# # Register your models here.

# # Register your models here.

# admin.site.register(ToDolist)
# admin.site.register(Item)





# @admin.register(Product)
# class ProductAdmin(admin.ModelAdmin):
#     list_display = ['id', 'name', 'price', 'created_at']


# @admin.register(ContactMessage)
# class ContactMessageAdmin(admin.ModelAdmin):
#     # Columns to show in list view
#     list_display = ['name', 'email', 'subject', 'date_sent', 'is_read']
    
#     # Add filters on the right side
#     list_filter = ['is_read', 'date_sent']
    
#     # Search bar
#     search_fields = ['name', 'email', 'subject', 'message']
    
#     # Make date_sent read-only
#     readonly_fields = ['date_sent']
    
#     # Make message field bigger
#     fields = ['name', 'email', 'subject', 'message', 'date_sent', 'is_read']
    
#     # Default ordering (newest first)
#     ordering = ['-date_sent']
    
#     # Add "Mark as Read" action
#     actions = ['mark_as_read']

#     def mark_as_read(self, request, queryset):
#         queryset.update(is_read=True)
#     mark_as_read.short_description = "Mark selected messages as Read"





#     # ====================== ORDER ADMIN ======================
# @admin.register(Order)
# class OrderAdmin(admin.ModelAdmin):

#     list_display = [
#         'reference',
#         'email',
#         'full_name',
#         'amount_display',
#         'status',
#         'verified',
#         'purchase_status',
#         'created_at'
#     ]

#     list_filter = [
#         'status',
#         'verified',
#         'purchase_completed',
#         'created_at'
#     ]

#     search_fields = [
#         'reference',
#         'email',
#         'full_name',
#         'phone'
#     ]

#     readonly_fields = [
#         'reference',
#         'created_at',
#         'updated_at'
#     ]

#     ordering = ['-created_at']

#     fieldsets = (
#         ('Customer Information', {
#             'fields': (
#                 'user',
#                 'full_name',
#                 'email',
#                 'phone'
#             )
#         }),

#         ('Payment Information', {
#             'fields': (
#                 'amount',
#                 'reference',
#                 'paystack_reference',
#                 'status',
#                 'verified'
#             )
#         }),

#         ('Purchase Status', {
#             'fields': (
#                 'purchase_completed',
#             )
#         }),

#         ('Timestamps', {
#             'fields': (
#                 'created_at',
#                 'updated_at'
#             ),
#             'classes': ('collapse',)
#         }),
#     )

#     def amount_display(self, obj):
#         return f"₦{obj.amount:,}"

#     amount_display.short_description = "Amount"

#     def purchase_status(self, obj):

#         if obj.verified and not obj.purchase_completed:
#             return "⚠ Recovery Needed"

#         return "✅ Completed"

#     purchase_status.short_description = "Purchase Status"

#     actions = [
#         'mark_as_verified',
#         'recover_failed_purchase'
#     ]

#     def mark_as_verified(self, request, queryset):

#         queryset.update(
#             verified=True,
#             status='paid'
#         )

#     mark_as_verified.short_description = (
#         "Mark selected orders as Verified & Paid"
#     )

#     def recover_failed_purchase(
#         self,
#         request,
#         queryset
#     ):

#         recovered = 0

#         for order in queryset:

#             if (
#                 order.verified and
#                 not order.purchase_completed
#             ):

#                 order.purchase_completed = True
#                 order.status = 'completed'

#                 order.save()

#                 recovered += 1

#         self.message_user(
#             request,
#             f"{recovered} order(s) recovered successfully."
#         )

#     recover_failed_purchase.short_description = (
#         "Recover Failed Purchases"
#     )



# Custom admin dashboard is used instead of Django Admin.