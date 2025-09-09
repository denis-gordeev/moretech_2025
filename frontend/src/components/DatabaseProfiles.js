import React, { useState, useEffect } from 'react';
import { Database, Plus, Trash2, RefreshCw, CheckCircle, AlertCircle } from 'lucide-react';
import { queryAnalyzerAPI } from '../services/api';

const DatabaseProfiles = ({ onProfileSelect, selectedProfile }) => {
  const [profiles, setProfiles] = useState([]);
  const [isLoading, setIsLoading] = useState(false);
  const [showCreateForm, setShowCreateForm] = useState(false);
  const [error, setError] = useState(null);
  const [success, setSuccess] = useState(null);

  const [newProfile, setNewProfile] = useState({
    name: '',
    host: '',
    port: 5432,
    database: '',
    username: '',
    password: ''
  });

  useEffect(() => {
    loadProfiles();
  }, []);

  const loadProfiles = async () => {
    try {
      setIsLoading(true);
      const response = await fetch('http://localhost:8000/database/profiles');
      const data = await response.json();
      
      if (data.status === 'success') {
        setProfiles(data.profiles);
      } else {
        setError('Failed to load profiles');
      }
    } catch (error) {
      console.error('Failed to load profiles:', error);
      setError('Failed to load profiles');
    } finally {
      setIsLoading(false);
    }
  };

  const createProfile = async (e) => {
    e.preventDefault();
    
    try {
      setIsLoading(true);
      setError(null);
      
      const formData = new FormData();
      Object.keys(newProfile).forEach(key => {
        formData.append(key, newProfile[key]);
      });

      const response = await fetch('http://localhost:8000/database/profiles', {
        method: 'POST',
        body: formData
      });
      
      const data = await response.json();
      
      if (data.status === 'success') {
        setSuccess('Database profile created successfully!');
        setShowCreateForm(false);
        setNewProfile({
          name: '',
          host: '',
          port: 5432,
          database: '',
          username: '',
          password: ''
        });
        await loadProfiles();
      } else {
        setError(data.message || 'Failed to create profile');
      }
    } catch (error) {
      console.error('Failed to create profile:', error);
      setError('Failed to create profile');
    } finally {
      setIsLoading(false);
    }
  };

  const deleteProfile = async (profileId) => {
    if (!window.confirm('Are you sure you want to delete this profile?')) {
      return;
    }
    
    try {
      setIsLoading(true);
      const response = await fetch(`http://localhost:8000/database/profiles/${profileId}`, {
        method: 'DELETE'
      });
      
      const data = await response.json();
      
      if (data.status === 'success') {
        setSuccess('Profile deleted successfully');
        await loadProfiles();
        
        // Clear selection if deleted profile was selected
        if (selectedProfile?.id === profileId) {
          onProfileSelect(null);
        }
      } else {
        setError(data.message || 'Failed to delete profile');
      }
    } catch (error) {
      console.error('Failed to delete profile:', error);
      setError('Failed to delete profile');
    } finally {
      setIsLoading(false);
    }
  };

  const selectProfile = (profile) => {
    onProfileSelect(profile);
    setSuccess(`Selected database: ${profile.name}`);
  };

  return (
    <div className="bg-white p-6 rounded-lg shadow-sm border border-gray-200">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center space-x-2">
          <Database className="w-5 h-5 text-gray-600" />
          <h3 className="text-lg font-semibold text-gray-900">Database Profiles</h3>
        </div>
        
        <button
          onClick={() => setShowCreateForm(!showCreateForm)}
          className="flex items-center space-x-1 px-3 py-1 bg-blue-600 text-white rounded-md hover:bg-blue-700 transition-colors"
        >
          <Plus className="w-4 h-4" />
          <span>Add Database</span>
        </button>
      </div>

      {/* Error/Success Messages */}
      {error && (
        <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-md flex items-center space-x-2">
          <AlertCircle className="w-4 h-4 text-red-600" />
          <span className="text-red-700 text-sm">{error}</span>
          <button onClick={() => setError(null)} className="ml-auto text-red-600 hover:text-red-800">×</button>
        </div>
      )}

      {success && (
        <div className="mb-4 p-3 bg-green-50 border border-green-200 rounded-md flex items-center space-x-2">
          <CheckCircle className="w-4 h-4 text-green-600" />
          <span className="text-green-700 text-sm">{success}</span>
          <button onClick={() => setSuccess(null)} className="ml-auto text-green-600 hover:text-green-800">×</button>
        </div>
      )}

      {/* Create Profile Form */}
      {showCreateForm && (
        <form onSubmit={createProfile} className="mb-6 p-4 bg-gray-50 rounded-lg">
          <h4 className="text-md font-medium text-gray-900 mb-3">Add New Database</h4>
          
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Profile Name</label>
              <input
                type="text"
                value={newProfile.name}
                onChange={(e) => setNewProfile({...newProfile, name: e.target.value})}
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                placeholder="My Production DB"
                required
              />
            </div>
            
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Host</label>
              <input
                type="text"
                value={newProfile.host}
                onChange={(e) => setNewProfile({...newProfile, host: e.target.value})}
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                placeholder="db.company.com"
                required
              />
            </div>
            
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Port</label>
              <input
                type="number"
                value={newProfile.port}
                onChange={(e) => setNewProfile({...newProfile, port: parseInt(e.target.value)})}
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                placeholder="5432"
                required
              />
            </div>
            
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Database</label>
              <input
                type="text"
                value={newProfile.database}
                onChange={(e) => setNewProfile({...newProfile, database: e.target.value})}
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                placeholder="analytics"
                required
              />
            </div>
            
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Username</label>
              <input
                type="text"
                value={newProfile.username}
                onChange={(e) => setNewProfile({...newProfile, username: e.target.value})}
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                placeholder="analyst"
                required
              />
            </div>
            
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Password</label>
              <input
                type="password"
                value={newProfile.password}
                onChange={(e) => setNewProfile({...newProfile, password: e.target.value})}
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                placeholder="••••••••"
                required
              />
            </div>
          </div>
          
          <div className="flex justify-end space-x-3 mt-4">
            <button
              type="button"
              onClick={() => setShowCreateForm(false)}
              className="px-4 py-2 text-gray-600 border border-gray-300 rounded-md hover:bg-gray-50"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={isLoading}
              className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:opacity-50"
            >
              {isLoading ? 'Creating...' : 'Create Profile'}
            </button>
          </div>
        </form>
      )}

      {/* Profiles List */}
      <div className="space-y-3">
        {isLoading && profiles.length === 0 ? (
          <div className="text-center py-4 text-gray-500">Loading profiles...</div>
        ) : profiles.length === 0 ? (
          <div className="text-center py-8 text-gray-500">
            <Database className="w-12 h-12 mx-auto mb-3 text-gray-300" />
            <p>No database profiles yet</p>
            <p className="text-sm">Add your first database to get started</p>
          </div>
        ) : (
          profiles.map((profile) => (
            <div
              key={profile.id}
              className={`p-3 border rounded-lg cursor-pointer transition-colors ${
                selectedProfile?.id === profile.id
                  ? 'border-blue-500 bg-blue-50'
                  : 'border-gray-200 hover:border-gray-300 hover:bg-gray-50'
              }`}
              onClick={() => selectProfile(profile)}
            >
              <div className="flex items-center justify-between">
                <div className="flex items-center space-x-3">
                  <Database className="w-4 h-4 text-gray-500" />
                  <div>
                    <h4 className="font-medium text-gray-900">{profile.name}</h4>
                    <p className="text-sm text-gray-500">
                      {profile.username}@{profile.host}:{profile.port}/{profile.database}
                    </p>
                    {profile.last_used && (
                      <p className="text-xs text-gray-400">
                        Last used: {new Date(profile.last_used).toLocaleString()}
                      </p>
                    )}
                  </div>
                </div>
                
                <div className="flex items-center space-x-2">
                  {profile.connection_test_passed && (
                    <CheckCircle className="w-4 h-4 text-green-500" title="Connection tested" />
                  )}
                  
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      deleteProfile(profile.id);
                    }}
                    className="p-1 text-gray-400 hover:text-red-600 transition-colors"
                    title="Delete profile"
                  >
                    <Trash2 className="w-4 h-4" />
                  </button>
                </div>
              </div>
            </div>
          ))
        )}
      </div>

      {/* Selected Profile Info */}
      {selectedProfile && (
        <div className="mt-4 p-3 bg-blue-50 border border-blue-200 rounded-lg">
          <div className="flex items-center space-x-2">
            <CheckCircle className="w-4 h-4 text-blue-600" />
            <span className="text-sm font-medium text-blue-900">
              Using: {selectedProfile.name}
            </span>
          </div>
          <p className="text-xs text-blue-700 mt-1">
            All queries will be analyzed against this database
          </p>
        </div>
      )}
    </div>
  );
};

export default DatabaseProfiles;
