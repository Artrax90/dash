// src/utils/scope.ts
/**
 * Hierarchical RBAC Scope Resolution & Isolation Engine (Frontend).
 * Supports matching by Building, Floor, Room, and Group paths across
 * the 3-level organization hierarchy (e.g. 'МНОК' -> 'МНОК / 1 этаж' -> 'МНОК / 1 этаж / 111').
 */

function getPathSegments(path: string): Set<string> {
  const clean = (path || '').trim().toLowerCase();
  if (!clean) return new Set();
  const segs = new Set<string>([clean]);
  const parts = clean.split('/').map(p => p.trim()).filter(Boolean);
  const norm = parts.join(' / ');
  segs.add(norm);
  if (parts.length >= 3) {
    const [bld, flr, rm] = [parts[0], parts[1], parts[2]];
    segs.add(bld);
    segs.add(flr);
    segs.add(rm);
    segs.add(`${bld} / ${flr}`);
    segs.add(`${bld} / ${flr} / ${rm}`);
    segs.add(`${bld} / ${rm}`);
    if (!rm.startsWith('кабинет')) {
      segs.add(`кабинет ${rm}`);
    } else {
      segs.add(rm.replace('кабинет', '').trim());
    }
  } else if (parts.length === 2) {
    const [bld, rm] = [parts[0], parts[1]];
    segs.add(bld);
    segs.add(rm);
    segs.add(`${bld} / ${rm}`);
    if (!rm.startsWith('кабинет')) {
      segs.add(`кабинет ${rm}`);
    } else {
      segs.add(rm.replace('кабинет', '').trim());
    }
  } else if (parts.length === 1) {
    const single = parts[0];
    if (single.startsWith('кабинет')) {
      segs.add(single.replace('кабинет', '').trim());
    } else {
      segs.add(`кабинет ${single}`);
    }
  }
  return segs;
}

export function isPathInScope(targetPath: string, allowedGroups?: string[] | null): boolean {
  if (!allowedGroups || allowedGroups.length === 0) return true;
  const cleanTarget = (targetPath || '').trim().toLowerCase();
  if (!cleanTarget) return false;

  const targetSegments = getPathSegments(cleanTarget);

  return allowedGroups.some(allowed => {
    const a = (allowed || '').trim().toLowerCase();
    if (!a) return false;
    if (cleanTarget === a) return true;
    if (cleanTarget.startsWith(a + ' /') || cleanTarget.startsWith(a + '/')) return true;
    if (a.startsWith(cleanTarget + ' /') || a.startsWith(cleanTarget + '/')) return true;
    const allowedSegments = getPathSegments(a);
    for (const seg of allowedSegments) {
      if (targetSegments.has(seg)) return true;
    }
    return false;
  });
}

export function isDeviceInAllowedGroups(
  device: { group?: string; groups?: string[]; building?: string; floor?: string; room?: string },
  allowedGroups?: string[] | null
): boolean {
  if (!allowedGroups || allowedGroups.length === 0) return true;

  let bld = (device.building || '').trim().toLowerCase();
  let flr = (device.floor || '').trim().toLowerCase();
  let rm = (device.room || '').trim().toLowerCase();
  const grp = (device.group || '').trim().toLowerCase();
  const grps = Array.isArray(device.groups) ? device.groups.map(g => String(g).trim().toLowerCase()) : [];

  const allPaths = new Set<string>();
  if (grp) {
    allPaths.add(grp);
    if (!bld && grp.includes('/')) {
      const parts = grp.split('/').map(s => s.trim());
      if (parts.length >= 3) {
        bld = parts[0];
        flr = parts[1];
        rm = parts[2];
      } else if (parts.length === 2) {
        bld = parts[0];
        rm = parts[1];
      }
    }
  }

  grps.forEach(g => { if (g) allPaths.add(g); });

  if (bld) {
    allPaths.add(bld);
    if (flr) {
      allPaths.add(`${bld} / ${flr}`);
      if (rm) {
        allPaths.add(`${bld} / ${flr} / ${rm}`);
      }
    } else if (rm) {
      allPaths.add(`${bld} / ${rm}`);
    }
  }

  return allowedGroups.some(allowed => {
    const a = (allowed || '').trim().toLowerCase();
    if (!a) return false;
    for (const p of allPaths) {
      if (p === a || p.startsWith(a + ' /') || p.startsWith(a + '/')) {
        return true;
      }
    }
    return false;
  });
}

export function isGroupInAllowedGroups(
  group: { name: string; building?: string; floor?: string; room?: string },
  allowedGroups?: string[] | null
): boolean {
  if (!allowedGroups || allowedGroups.length === 0) return true;

  let name = (group.name || '').trim().toLowerCase();
  let bld = (group.building || '').trim().toLowerCase();
  let flr = (group.floor || '').trim().toLowerCase();
  let rm = (group.room || '').trim().toLowerCase();

  const allPaths = new Set<string>();
  if (name) {
    allPaths.add(name);
    if (!bld && name.includes('/')) {
      const parts = name.split('/').map(s => s.trim());
      if (parts.length >= 3) {
        bld = parts[0];
        flr = parts[1];
        rm = parts[2];
      } else if (parts.length === 2) {
        bld = parts[0];
        rm = parts[1];
      }
    }
  }

  if (bld) {
    allPaths.add(bld);
    if (flr) {
      allPaths.add(`${bld} / ${flr}`);
      if (rm) {
        allPaths.add(`${bld} / ${flr} / ${rm}`);
      }
    } else if (rm) {
      allPaths.add(`${bld} / ${rm}`);
    }
  }

  return allowedGroups.some(allowed => {
    const a = (allowed || '').trim().toLowerCase();
    if (!a) return false;
    for (const p of allPaths) {
      if (p === a || p.startsWith(a + ' /') || p.startsWith(a + '/') || a.startsWith(p + ' /') || a.startsWith(p + '/')) {
        return true;
      }
    }
    return false;
  });
}

export function isBuildingVisibleInScope(buildingName: string, allowedGroups?: string[] | null): boolean {
  if (!allowedGroups || allowedGroups.length === 0) return true;
  const b = (buildingName || '').trim().toLowerCase();
  if (!b) return false;
  return allowedGroups.some(allowed => {
    const a = (allowed || '').trim().toLowerCase();
    if (!a) return false;
    return a === b || a.startsWith(b + ' /') || a.startsWith(b + '/') || b.startsWith(a + ' /') || b.startsWith(a + '/');
  });
}

export function isFloorVisibleInScope(buildingName: string, floorName: string, allowedGroups?: string[] | null): boolean {
  if (!allowedGroups || allowedGroups.length === 0) return true;
  const b = (buildingName || '').trim().toLowerCase();
  const f = (floorName || '').trim().toLowerCase();
  const fPath = `${b} / ${f}`;
  return allowedGroups.some(allowed => {
    const a = (allowed || '').trim().toLowerCase();
    if (!a) return false;
    return a === b || a === fPath || a.startsWith(fPath + ' /') || a.startsWith(fPath + '/') || fPath.startsWith(a + ' /');
  });
}

export function isRoomVisibleInScope(
  buildingName: string,
  floorName: string,
  roomName: string,
  allowedGroups?: string[] | null
): boolean {
  if (!allowedGroups || allowedGroups.length === 0) return true;
  const b = (buildingName || '').trim().toLowerCase();
  const f = (floorName || '').trim().toLowerCase();
  const r = (roomName || '').trim().toLowerCase();
  const fPath = `${b} / ${f}`;
  const rPath = (b && f && r) ? `${fPath} / ${r}` : `${b} / ${r}`;
  return allowedGroups.some(allowed => {
    const a = (allowed || '').trim().toLowerCase();
    if (!a) return false;
    return a === b || a === fPath || a === rPath || a === r;
  });
}export function isSuperAdminRole(role?: string | null): boolean {
  if (!role) return false;
  const r = role.toLowerCase().trim();
  return r === 'суперадминистратор' || r === 'superadmin' || r === 'root';
}

export function isFleetAdminRole(role?: string | null): boolean {
  if (!role) return false;
  const r = role.toLowerCase().trim();
  return r === 'администратор парка' || r === 'fleetadmin' || r === 'fleet administrator' || r === 'администратор';
}

export function canManageFleetGroups(role?: string | null): boolean {
  return isSuperAdminRole(role) || isFleetAdminRole(role);
}
