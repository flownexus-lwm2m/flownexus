.. SPDX-License-Identifier: Apache-2.0
   Copyright (c) 2026 Jonas Remmert

Access Control
==============

flownexus implements a multi-site access control system for organizing devices
and controlling user access. This is **not** a multi-tenant SaaS architecture
where multiple customers share a single database. Instead, flownexus is designed
to run as a single-tenant application on a dedicated server per customer, with
Sites providing internal organization for that customer's deployment.

Deployment Model
----------------

flownexus follows a **single-tenant per server** deployment model:

* Each customer runs their own flownexus instance on dedicated infrastructure
* Database isolation is physical — each deployment has its own isolated database
* No shared database or application layer between different customers
* Sites are internal organizational units, not customer boundaries

This architecture provides strong data isolation at the infrastructure level
while allowing flexible organization within each customer's deployment.

Overview
--------

Within a single deployment, the access control system is built around three core
concepts:

* **Sites**: Organizational units that group devices and control data visibility
* **Roles**: Hierarchical permission levels (Site User, Site Admin, Global Admin)
* **Permissions**: Granular access to features and operations within a Site

This design allows organizations to organize large device deployments across
multiple locations while controlling which users can access which devices.

Roles and Permissions
---------------------

The following table shows the access levels for each role:

+-------------------------+-----------+------------+--------------+
| Feature                 | Site User | Site Admin | Global Admin |
+=========================+===========+============+==============+
| Devices tab             | ✓         | ✓          | ✓            |
+-------------------------+-----------+------------+--------------+
| Firmware tab            | ✗         | ✓          | ✓            |
+-------------------------+-----------+------------+--------------+
| Data tab                | ✓         | ✓          | ✓            |
+-------------------------+-----------+------------+--------------+
| Permissions tab         | ✗         | ✗          | ✓            |
+-------------------------+-----------+------------+--------------+
| Manage Firmware         | ✗         | ✓          | ✓            |
+-------------------------+-----------+------------+--------------+
| Perform Operations      | ✗         | ✓          | ✓            |
+-------------------------+-----------+------------+--------------+
| Manage Devices          | ✗         | ✗          | ✓            |
+-------------------------+-----------+------------+--------------+
| Assign Devices to Sites | ✗         | ✗          | ✓            |
+-------------------------+-----------+------------+--------------+
| Create Users            | ✗         | ✗          | ✓            |
+-------------------------+-----------+------------+--------------+
| Assign Permissions      | ✗         | ✗          | ✓            |
+-------------------------+-----------+------------+--------------+

Users are assigned to Sites through **SiteMembership** with specific roles:

**Global Admin**
  Superuser with full system access including creating users, assigning
  permissions, and accessing Django admin. Can manage all Sites.

**Site Admin**
  Full access within their assigned Sites including firmware management
  and device operations. Cannot create users or reassign devices between
  Sites from the Permissions tab.

**Site User**
  Read-only access to dashboards and telemetry within their assigned Sites.
  Cannot view Firmware tab or perform operations. Typical use: Monitoring
  personnel, data analysts.

Data visibility is controlled per Site. Users cannot see devices from Sites
they don't belong to.

Site Organization
-----------------

Within a single flownexus deployment, each **Site** represents an internal
organizational grouping — similar to how you might organize resources by
building, department, or function within one company:

* **Devices** (Endpoints) belong to exactly one Site
* **Users** can be members of multiple Sites
* **Data** visibility is controlled per Site (users only see their assigned Sites)
* **Firmware** binaries can be shared across Sites within the same deployment
* **Firmware updates** are tracked per Site

Sites help manage large device deployments by grouping related endpoints
together. For example:

* **Physical locations**: Building A, Building B, Warehouse North
* **Functional areas**: Production Line 1, HVAC Systems, Security Devices
* **Organizational units**: Engineering Department, Operations Floor



Feature Permissions
-------------------

Per-site permissions control access to functional areas:

**View Permissions**
  Control access to different sections of the web interface:

  * **Devices tab**: View device status and basic information
  * **Firmware tab**: Access firmware management and FOTA updates
  * **Data tab**: Use advanced telemetry filtering and visualization tools
  * **Permissions tab**: Global Admin only - manage users and device routing

**Operational Permissions**
  Control what actions users can perform:

  * **Manage Firmware**: Upload and delete firmware binaries
  * **Perform Operations**: Write resources and execute commands on devices
  * **Manage Devices**: Global Admin only for assigning and transferring devices between Sites

Devices Tab (Read-Only View)
-------------------------------

The Devices tab provides a read-only informational view of all devices within
the user's accessible Sites. All roles (Site User, Site Admin, Global Admin)
can access this tab to view:

* Device status and connectivity state
* Last seen timestamps and telemetry summary
* Basic device information (name, URN, model)
* Current Site assignment

**Filtering**: Devices are automatically filtered by the user's active Site
context. Users only see devices from Sites they are members of. Global Admins
can optionally view all devices across all Sites.

**Actions**: This tab is strictly read-only. Device operations (Write, Execute)
and configuration changes are performed from the Firmware tab or device detail
views (requires appropriate permissions).

User Management and Permissions
--------------------------------

The Permissions tab serves as the centralized hub for Global Admin routing,
providing a unified interface for managing both user assignments and device
routing within Sites.

**Two-Section Layout**:

1. **User Roles Section**: Manage user access and permissions
   - Create new users and assign initial passwords
   - Assign users to Sites with specific roles (Site User or Site Admin)
   - Configure per-site permissions (view tabs, manage firmware, etc.)
   - Revoke Site memberships

2. **Device Routing Section**: Manage device-to-Site assignments
   - View unassigned devices (devices with ``site__isnull=True``)
   - Assign devices to specific Sites
   - Transfer devices between Sites
   - Bulk assignment operations for efficient device onboarding

This unified approach ensures Global Admins can efficiently manage access
control from a single interface without navigating between separate views.

The current implementation keeps device routing and unassigned-device handling
in the Global Admin Permissions tab only. Site Admins can work within their
assigned Sites, but cannot move devices between Sites through the web UI.

Unassigned Device Handling
..........................

**Operational State**: Unassigned devices (those with ``site__isnull=True``) remain
fully operational and are not quarantined. They continue to:

* Ingest telemetry data (Resources)
* Trigger events and alerts
* Respond to LwM2M operations
* Maintain normal device communication

**Data Visibility**: Because unassigned devices have no Site context, their telemetry
and events are only visible to Global Admins. Standard users (Site Users and Site
Admins) cannot access unassigned device data since they lack the required site
membership context. This ensures data isolation while allowing devices to operate
during onboarding or site reassignment workflows.

Site Admin User Visibility
..........................

Site Admins have limited visibility of other users:

* Can only view users who are members of their Sites
* Cannot see users from other Sites
* Cannot modify user accounts or permissions

User Self-Service
.................

All users can perform limited self-service actions:

* Change their own password via the profile page
* View their current Site memberships
* Switch between assigned Sites using the site selector

Django Admin Fallback
......................

The Django admin interface (``/admin/``) is available as a fallback for
advanced administrative tasks. It is restricted to Global Admins only.
Regular users and Site Admins cannot access the admin panel. All common
user management tasks should be performed through the Permissions tab.

Site Context and Data Visibility
--------------------------------

Site Context Switching
......................

Users belonging to multiple Sites see a site switcher in the top navigation
bar. The current Site context filters all data and operations:

* Dashboard shows only devices from the current Site
* Firmware updates are filtered by Site
* Operations only affect devices in the current Site

Navigation menus adapt dynamically based on the user's permissions for the
active Site. If a user lacks permission for a feature, the corresponding
navigation item is hidden.

Data Visibility
...............

Within a single deployment, the system controls data visibility per Site:

* Users cannot see devices from Sites they don't belong to
* API responses are filtered by Site membership
* Database queries automatically apply Site filters
* Multi-site users see aggregated data when "All Sites" is selected



Implementation
--------------

The access control system is implemented through several components:

Models
......

**Site**
  Represents an organizational grouping within a single deployment.
  Contains name, description, and active status. Endpoints have a ForeignKey
  to Site. Sites are not used for customer isolation — that is handled by
  separate server instances.

**SiteMembership**
  Links users to Sites with roles and permissions. Contains:

  * User and Site references
  * Role (ADMIN or USER)
  * View permissions (overview, firmware, data_analysis)
  * Operational permissions (manage_firmware, perform_operations, manage_devices)

Middleware
..........

**SiteContextMiddleware**
  Sets the current Site context for each request:

  * Determines active Site from session or defaults to first available
  * Loads user's Site memberships
  * Validates user has access to requested Site
  * Makes Site context available to views and templates

Context Processors
..................

**site_context**
  Provides permission variables to all templates:

  * ``can_view_devices``, ``can_view_firmware``, ``can_view_data_analysis``
  * ``can_manage_firmware``, ``can_perform_operations``, ``can_manage_devices``
  * ``site_role``, ``current_site``, ``available_sites``
  * ``is_global_admin``, ``show_all_devices``

Views
......

Each view checks permissions before processing:

.. code-block:: python

   def _check_site_permission(request, permission_name):
       if request.user.is_superuser:
           return True
       # Check site membership permissions
       if hasattr(request, 'site_membership') and request.site_membership:
           return getattr(request.site_membership, permission_name, False)
       return False

Implementation Hints
....................

The following patterns guide the implementation of the access control views:

**Devices List View (Read-Only)**

The Devices tab should be implemented as a read-only list view with site-based
filtering:

* QuerySet filtering: ``Endpoint.objects.filter(site__in=user.site_memberships.values('site'))``
* For Global Admins: optionally show all devices with ``Endpoint.objects.all()``
* Remove all POST handling and form logic — this view is strictly for display
* Display device status, connectivity info, and current Site assignment

**Permissions View (Global Admin Only)**

The unified Permissions tab requires Global Admin access and provides two
functional areas:

* **Access Control**: Restrict the entire view using ``@user_passes_test(lambda u: u.is_superuser)``
* **Dual-Panel Layout**: Present two distinct sections or sub-tabs:

  - User Roles: Queryset ``User.objects.all()`` for user management
  - Device Routing: Queryset ``Endpoint.objects.all()`` with highlighting for
    unassigned devices (``site__isnull=True``)

* **POST Security**: In assignment handlers, explicitly verify
  ``request.user.is_superuser`` and return ``HttpResponseForbidden()`` if check fails
  to protect against request spoofing outside the UI

**Querying Downstream Models**

Models like Resource, Event, and FirmwareUpdate do not have a direct Site foreign
key. Always traverse the ``endpoint__site`` relationship **and** use
``select_related`` to prevent both data leaks and N+1 query performance bottlenecks:

.. code-block:: python

   # Correct: Filter by site AND use select_related for performance
   resources = Resource.objects.select_related('endpoint__site').filter(
       endpoint__site__in=user.site_memberships.values('site')
   )

   events = Event.objects.select_related('endpoint__site').filter(
       endpoint__site__in=user.site_memberships.values('site')
   )

   firmware_updates = FirmwareUpdate.objects.select_related('endpoint__site').filter(
       endpoint__site__in=user.site_memberships.values('site')
   )

**Critical**: Omitting the ``endpoint__site__in`` filter exposes all telemetry to
all users (data leak). Omitting ``select_related`` causes N+1 queries (10,001
queries for 10,000 resources instead of 1).

Testing with Mock Scenarios
---------------------------

The mock simulation system provides scenario-based configurations for testing
access control. See :doc:`devtools` for details on the multi-site scenario
which creates multiple Sites with different user roles and permissions for
comprehensive RBAC testing.
