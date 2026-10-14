import { useState, useEffect } from 'react';
import { fetchAdminSettings, saveAdminSettings } from '../../../utils/api';

export default function SettingsTab({ authHeaders }) {
  const [notificationEmails, setNotificationEmails] = useState('');
  const [settingsSaving, setSettingsSaving] = useState(false);
  const [settingsMessage, setSettingsMessage] = useState(null);

  const loadSettings = async () => {
    try {
      const res = await fetchAdminSettings(authHeaders);
      const data = res.data;
      setNotificationEmails(data.notification_emails || '');
    } catch (err) {
      console.error('Failed to load settings:', err);
    }
  };

  const saveNotificationEmails = async () => {
    setSettingsSaving(true);
    setSettingsMessage(null);
    try {
      const res = await saveAdminSettings(authHeaders, { notification_emails: notificationEmails });
      const data = res.data;
      if (data.success) {
        setSettingsMessage({ type: 'success', text: 'Notification emails saved successfully!' });
      } else {
        setSettingsMessage({ type: 'error', text: data.error || 'Failed to save settings' });
      }
    } catch (err) {
      setSettingsMessage({ type: 'error', text: 'Failed to save settings' });
    }
    setSettingsSaving(false);
  };

  useEffect(() => {
    loadSettings();
  }, []);

  return (
    <div className="space-y-6">
      <div>
        <h3 className="font-medium text-gray-900 mb-4">Email Notifications</h3>
        <div className="bg-gray-50 p-4 rounded space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Notification Email Addresses
            </label>
            <p className="text-sm text-gray-500 mb-2">
              Enter email addresses to receive notifications when users submit text requests or feedback.
              Separate multiple addresses with commas.
            </p>
            <textarea
              value={notificationEmails}
              onChange={e => setNotificationEmails(e.target.value)}
              placeholder="admin@example.com, scholar@university.edu"
              className="w-full border rounded px-3 py-2 text-sm"
              rows={3}
            />
          </div>

          {settingsMessage && (
            <div className={`text-sm p-2 rounded ${
              settingsMessage.type === 'success'
                ? 'bg-amber-100 text-amber-700'
                : 'bg-red-100 text-red-700'
            }`}>
              {settingsMessage.text}
            </div>
          )}

          <button
            onClick={saveNotificationEmails}
            disabled={settingsSaving}
            className="px-4 py-2 bg-red-700 text-white rounded hover:bg-red-800 disabled:opacity-50"
          >
            {settingsSaving ? 'Saving...' : 'Save Email Settings'}
          </button>
        </div>
      </div>

      <div className="text-sm text-gray-500 bg-amber-50 p-4 rounded">
        <strong>Note:</strong> Email notifications will be sent when:
        <ul className="list-disc ml-5 mt-2 space-y-1">
          <li>A user submits a request for a new text to be added</li>
          <li>A user submits feedback through the Help page</li>
        </ul>
      </div>
    </div>
  );
}
