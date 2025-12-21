# 👤 User Management Guide

## Default Admin Account

**Username:** `9542`  
**Password:** `9542`

This account is automatically created when the app starts for the first time and has permanent access (no expiration).

## Creating Users

1. **Login** as admin (username: `9542`, password: `9542`)
2. Go to **Admin** page
3. In **User Management** section:
   - Enter **Username**
   - Enter **Password**
   - Enter **Subscription Days** (e.g., 30, 60, 90, 365)
   - Click **"Create User"**

## Managing Users

### Update Subscription
- Enter number of days in the input field next to the user
- Click **"Update"** button
- This will **extend** the subscription from the current expiration date

### Activate/Deactivate Users
- Click **"Deactivate"** to temporarily disable a user
- Click **"Activate"** to re-enable a deactivated user
- Admin user cannot be deactivated

## User Status

- **✅ Active:** User can login and use the app
- **❌ Expired:** Subscription has expired, user cannot login
- **Days Remaining:** Shows how many days left in subscription

## Login

Users login with:
- **Username** (not email)
- **Password**

## Subscription System

- Each user has a subscription period (in days)
- Subscription expires after the specified number of days
- Admin can extend subscriptions at any time
- Admin user (`9542`) has permanent access

## Example Workflow

1. Admin creates user "john" with 30 days subscription
2. User "john" logs in with username/password
3. After 30 days, subscription expires
4. Admin extends subscription by adding more days
5. User can login again

