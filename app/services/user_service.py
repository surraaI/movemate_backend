import json

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.security import hash_password, verify_password
from app.models.enums import UserRole, UserStatus
from app.models.profile import AdminProfile, CommuterProfile, DriverProfile
from app.models.user import User
from app.schemas.user import ChangePasswordRequest, UserOut, UserUpdate


def user_to_out(user: User) -> UserOut:
    return UserOut.model_validate(user)


def get_me(user: User) -> UserOut:
    return user_to_out(user)


def update_me(db: Session, user: User, data: UserUpdate) -> UserOut:
    if data.full_name is not None:
        user.full_name = data.full_name
    if data.phone_number is not None:
        user.phone_number = data.phone_number

    if user.role == UserRole.COMMUTER and user.commuter_profile:
        if data.commuter_preferred_route_id is not None:
            user.commuter_profile.preferred_route_id = data.commuter_preferred_route_id
        if data.commuter_notes is not None:
            user.commuter_profile.notes = data.commuter_notes
    elif user.role == UserRole.DRIVER and user.driver_profile:
        if data.driver_license_number is not None:
            user.driver_profile.license_number = data.driver_license_number
        if data.driver_employee_id is not None:
            user.driver_profile.employee_id = data.driver_employee_id
        if data.driver_assigned_vehicle_id is not None:
            user.driver_profile.assigned_vehicle_id = data.driver_assigned_vehicle_id
    elif user.role == UserRole.ADMIN and user.admin_profile:
        if data.admin_department is not None:
            user.admin_profile.department = data.admin_department
        if data.admin_permissions is not None:
            user.admin_profile.permissions = json.dumps(data.admin_permissions)

    db.add(user)
    db.commit()
    db.refresh(user)
    return user_to_out(user)


def change_password(db: Session, user: User, data: ChangePasswordRequest) -> None:
    if not verify_password(data.current_password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect",
        )
    user.password_hash = hash_password(data.new_password)
    db.add(user)
    db.commit()


def deactivate_account(db: Session, user: User) -> None:
    user.status = UserStatus.INACTIVE
    db.add(user)
    db.commit()
