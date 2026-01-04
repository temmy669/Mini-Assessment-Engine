from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.html import format_html
from .models import User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = [
        'username', 'email', 'role_badge', 'student_id',
        'is_active', 'date_joined'
    ]
    list_filter = ['role', 'is_active', 'is_staff', 'date_joined']
    search_fields = ['username', 'email', 'first_name', 'last_name', 'student_id']
    
    fieldsets = list(BaseUserAdmin.fieldsets) + [
        ('Additional Info', {
            'fields': ('role', 'student_id')
        }),
    ]
    
    add_fieldsets = list(BaseUserAdmin.add_fieldsets) + [
        ('Additional Info', {
            'fields': ('email', 'role', 'student_id')
        }),
    ]
    
    def role_badge(self, obj):
        colors = {
            'STUDENT': '#2196F3',
            'INSTRUCTOR': '#4CAF50',
            'ADMIN': '#FF9800'
        }
        color = colors.get(obj.role, 'gray')
        return format_html(
            '<span style="background-color: {}; color: white; '
            'padding: 3px 10px; border-radius: 3px;">{}</span>',
            color, obj.get_role_display()
        )
    role_badge.short_description = 'Role'