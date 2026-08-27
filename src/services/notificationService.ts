/**
 * Browser Desktop & OS Notification Service (Chrome / Google / Edge / Firefox)
 * Handles permissions, native desktop push popups for critical alerts, hardware mismatches, and power events.
 */

export interface DesktopNotificationOptions {
  body?: string;
  icon?: string;
  tag?: string;
  requireInteraction?: boolean;
  silent?: boolean;
  data?: any;
}

class BrowserNotificationService {
  private hasPrompted = false;

  /**
   * Check if browser supports Notification API
   */
  public isSupported(): boolean {
    return typeof window !== 'undefined' && 'Notification' in window;
  }

  /**
   * Current notification permission: 'default' | 'granted' | 'denied'
   */
  public getPermission(): NotificationPermission {
    if (!this.isSupported()) return 'denied';
    return Notification.permission;
  }

  /**
   * Request notification permission from the user / browser
   */
  public async requestPermission(): Promise<boolean> {
    if (!this.isSupported()) return false;
    try {
      if (Notification.permission === 'default') {
        const result = await Notification.requestPermission();
        return result === 'granted';
      }
      return Notification.permission === 'granted';
    } catch (err) {
      console.warn('[NotificationService] Permission request failed:', err);
      return false;
    }
  }

  /**
   * Proactively ask user for notification permission on initial interaction / app startup
   */
  public initAutoPrompt() {
    if (this.hasPrompted || !this.isSupported()) return;
    this.hasPrompted = true;
    if (Notification.permission === 'default') {
      // Delay slightly so the page finishes loading first
      setTimeout(() => {
        this.requestPermission();
      }, 1500);
    }
  }

  /**
   * Show a native Desktop OS Popup Notification
   */
  public showNotification(title: string, options?: DesktopNotificationOptions): Notification | null {
    if (!this.isSupported() || Notification.permission !== 'granted') {
      return null;
    }

    try {
      const notification = new Notification(title, {
        icon: options?.icon || '/favicon.ico',
        badge: '/favicon.ico',
        body: options?.body || '',
        tag: options?.tag,
        requireInteraction: options?.requireInteraction ?? false,
        silent: options?.silent ?? false,
        data: options?.data
      });

      notification.onclick = () => {
        window.focus();
        notification.close();
      };

      // Auto close after 10 seconds if not clicked
      setTimeout(() => {
        try {
          notification.close();
        } catch {}
      }, 10000);

      return notification;
    } catch (err) {
      console.warn('[NotificationService] Failed to show notification:', err);
      return null;
    }
  }

  /**
   * Specific notification for Workstation Alerts (Hardware, Power, Security)
   */
  public notifyAlert(alert: { id?: string; type?: string; severity?: string; device?: string; description?: string }) {
    const isCritical = alert.severity === 'Critical';
    const title = `${isCritical ? '🚨 КРИТИЧЕСКИЙ АЛЕРТ' : '⚠️ Оповещение'} [${alert.device || 'ПК'}]`;
    const body = `${alert.type || 'Системное событие'}\n${alert.description || ''}`;

    this.showNotification(title, {
      body,
      tag: alert.id || `alert-${Date.now()}`,
      requireInteraction: isCritical
    });
  }

  /**
   * Specific notification for Hardware Discrepancies
   */
  public notifyHardwareMismatch(device: string, component: string, change: string) {
    this.showNotification(`🚨 Изменение оборудования: ${device}`, {
      body: `Компонент: ${component}\n${change}`,
      tag: `hw-${device}-${Date.now()}`,
      requireInteraction: true
    });
  }
}

export const notificationService = new BrowserNotificationService();
