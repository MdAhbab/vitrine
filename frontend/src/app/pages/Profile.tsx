import { useState, useEffect } from 'react';
import { useStore, PLAN_DETAILS, type SellerPlan, type User } from '../lib/store';
import { api, mediaUrl } from '../lib/api';
import {
  User as UserIcon,
  Settings as SettingsIcon,
  Shield,
  Coins,
  Lock,
  Upload,
  MapPin,
  CreditCard,
  ArrowLeft,
  Palette,
  Eye,
  Check,
  ChevronRight,
  ExternalLink,
  Crown,
  AlertCircle,
  Activity,
  UserCheck
} from 'lucide-react';

export function Profile({ userId: routeUserId, onBack }: { userId?: string; onBack?: () => void }) {
  const { user: currentUser, updateUser, setUserPlan } = useStore();
  const [profileUser, setProfileUser] = useState<any | null>(null);
  const [listings, setListings] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Profile view tabs: 'view' (public view) or 'settings' (owner settings)
  const isOwner = !routeUserId || routeUserId === currentUser?.id;
  const targetUserId = routeUserId || currentUser?.id;

  const [activeTab, setActiveTab] = useState<'view' | 'settings'>(isOwner ? 'settings' : 'view');
  const [settingsSection, setSettingsSection] = useState<'profile' | 'security' | 'preferences' | 'ai' | 'billing'>('profile');

  // Edit Profile form fields
  const [displayName, setDisplayName] = useState('');
  const [bio, setBio] = useState('');
  const [location, setLocation] = useState('');
  const [avatarUrl, setAvatarUrl] = useState('');
  const [minimalProfile, setMinimalProfile] = useState(false);
  const [themeDefault, setThemeDefault] = useState('dark');
  const [profileSaving, setProfileSaving] = useState(false);
  const [profileSuccess, setProfileSuccess] = useState(false);

  // Change Password form fields
  const [currentPassword, setCurrentPassword] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [passwordSaving, setPasswordSaving] = useState(false);
  const [passwordError, setPasswordError] = useState<string | null>(null);
  const [passwordSuccess, setPasswordSuccess] = useState(false);

  // Billing & Subscriptions fields
  const [billingInfo, setBillingInfo] = useState<any>(null);
  const [billingLoading, setBillingLoading] = useState(false);

  // Uploading status
  const [uploading, setUploading] = useState(false);

  // Load profile user and listings
  const loadProfile = async () => {
    if (!targetUserId) {
      setLoading(false);
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const data = await api.getProfile(targetUserId);
      setProfileUser(data);
      setListings(data.listings || []);
      
      // Seed form values if owner
      if (isOwner) {
        setDisplayName(data.name || '');
        setBio(data.bio || '');
        setLocation(data.location || '');
        setAvatarUrl(data.avatar || '');
        setMinimalProfile(data.minimalProfile || false);
        setThemeDefault(data.themeDefault || 'dark');
      }
    } catch (err: any) {
      console.error(err);
      setError(err.message || 'Failed to load profile');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadProfile();
  }, [targetUserId, currentUser?.id]);

  // Load Billing details
  const loadBilling = async () => {
    if (!isOwner) return;
    setBillingLoading(true);
    try {
      const data = await api.getBilling();
      setBillingInfo(data);
    } catch (err) {
      console.error('Failed to load billing info', err);
    } finally {
      setBillingLoading(false);
    }
  };

  useEffect(() => {
    if (activeTab === 'settings' && settingsSection === 'billing') {
      loadBilling();
    }
  }, [activeTab, settingsSection]);

  // Handle avatar image upload
  const handleAvatarUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploading(true);
    try {
      const res = await api.uploadFile(file, 'avatars');
      setAvatarUrl(res.url);
      
      // Auto-save the new avatar URL immediately
      if (currentUser) {
        const updatedUser = await api.updateProfile({ avatar_url: res.url });
        updateUser(updatedUser);
      }
    } catch (err: any) {
      alert(err.message || 'Failed to upload avatar picture');
    } finally {
      setUploading(false);
    }
  };

  // Save profile updates
  const handleSaveProfile = async (e: React.FormEvent) => {
    e.preventDefault();
    setProfileSaving(true);
    setProfileSuccess(false);
    try {
      const payload = {
        display_name: displayName,
        bio: bio,
        location: location,
        avatar_url: avatarUrl,
        minimal_profile: minimalProfile,
        theme_default: themeDefault
      };
      const updatedUser = await api.updateProfile(payload);
      updateUser(updatedUser);
      
      // Update local profile user object
      setProfileUser((prev: any) => ({
        ...prev,
        name: updatedUser.name,
        bio: updatedUser.bio,
        location: updatedUser.location,
        avatar: updatedUser.avatar,
        minimalProfile: updatedUser.minimalProfile,
        themeDefault: updatedUser.themeDefault
      }));

      // Apply theme preference immediately
      if (updatedUser.themeDefault === 'light') {
        document.documentElement.classList.remove('dark');
      } else {
        document.documentElement.classList.add('dark');
      }

      setProfileSuccess(true);
      setTimeout(() => setProfileSuccess(false), 3000);
    } catch (err: any) {
      alert(err.message || 'Failed to update profile settings');
    } finally {
      setProfileSaving(false);
    }
  };

  // Save password updates
  const handleChangePassword = async (e: React.FormEvent) => {
    e.preventDefault();
    setPasswordError(null);
    setPasswordSuccess(false);

    if (newPassword !== confirmPassword) {
      setPasswordError('New passwords do not match');
      return;
    }

    if (newPassword.length < 6) {
      setPasswordError('New password must be at least 6 characters');
      return;
    }

    setPasswordSaving(true);
    try {
      await api.changePassword({
        current_password: currentPassword,
        new_password: newPassword
      });
      setPasswordSuccess(true);
      setCurrentPassword('');
      setNewPassword('');
      setConfirmPassword('');
      setTimeout(() => setPasswordSuccess(false), 4000);
    } catch (err: any) {
      setPasswordError(err.message || 'Incorrect current password');
    } finally {
      setPasswordSaving(false);
    }
  };

  // Switch plans
  const handlePlanChange = async (tier: SellerPlan) => {
    try {
      await setUserPlan(tier);
      // reload billing list
      await loadBilling();
      // refresh global session info
      const me = await api.me();
      updateUser(me);
    } catch (err: any) {
      alert(err.message || 'Failed to update subscription tier');
    }
  };

  // Determine if ads should be shown (free plan users only)
  const showAds = !currentUser || currentUser.plan === 'free';

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[60vh] gap-3">
        <div className="w-10 h-10 border-2 border-accent border-t-transparent rounded-full animate-spin"></div>
        <div className="font-mono text-xs text-text-muted">Loading Vitrine Profile...</div>
      </div>
    );
  }

  if (error || !profileUser) {
    return (
      <div className="max-w-xl mx-auto px-4 py-20 text-center">
        <AlertCircle size={40} className="text-danger mx-auto mb-4" />
        <h2 className="font-serif text-2xl">Profile Not Found</h2>
        <p className="text-text-muted mt-2">{error || 'This user profile does not exist or has been removed.'}</p>
        <button onClick={onBack || (() => window.location.hash = '')} className="mt-6 inline-flex items-center gap-2 px-5 h-10 rounded-xl bg-surface hairline text-sm hover:border-accent transition-colors">
          <ArrowLeft size={14} /> Back to Vitrine
        </button>
      </div>
    );
  }

  const isSeller = profileUser.role === 'seller';
  const displayMinimal = profileUser.minimalProfile;

  return (
    <main className="max-w-[1200px] mx-auto px-4 sm:px-6 lg:px-8 pt-8 pb-24">
      {/* Back button */}
      <div className="mb-6 flex justify-between items-center">
        <button onClick={onBack || (() => window.history.back())} className="inline-flex items-center gap-2 text-xs font-mono text-text-muted hover:text-text transition-colors">
          <ArrowLeft size={12} /> Back
        </button>

        {isOwner && (
          <div className="flex items-center gap-2 p-1 hairline rounded-xl bg-surface">
            <button
              onClick={() => setActiveTab('view')}
              className={`px-4 py-1.5 rounded-lg text-xs font-medium transition-colors flex items-center gap-1.5 ${
                activeTab === 'view' ? 'bg-text text-bg' : 'text-text-muted hover:text-text'
              }`}
            >
              <Eye size={12} /> Public Preview
            </button>
            <button
              onClick={() => setActiveTab('settings')}
              className={`px-4 py-1.5 rounded-lg text-xs font-medium transition-colors flex items-center gap-1.5 ${
                activeTab === 'settings' ? 'bg-text text-bg' : 'text-text-muted hover:text-text'
              }`}
            >
              <SettingsIcon size={12} /> Settings & Billing
            </button>
          </div>
        )}
      </div>

      {activeTab === 'view' ? (
        /* ==================== PUBLIC PROFILE PREVIEW ==================== */
        <div className="space-y-8 fade-in">
          {/* Header Banner */}
          <section className="relative rounded-3xl overflow-hidden bg-surface hairline p-6 sm:p-10 flex flex-col md:flex-row gap-6 md:gap-10 items-center">
            {/* Cover Glow Background */}
            <div className="absolute inset-0 opacity-10 pointer-events-none bg-gradient-to-tr from-accent via-transparent to-accent-soft" />
            
            {/* Avatar image */}
            <div className="relative w-28 h-28 sm:w-36 sm:h-36 rounded-2xl overflow-hidden bg-surface-2 hairline shrink-0">
              {profileUser.avatar ? (
                <img src={mediaUrl(profileUser.avatar)} alt={profileUser.name} className="w-full h-full object-cover" />
              ) : (
                <div className="w-full h-full flex items-center justify-center bg-accent-soft/20 text-accent font-serif text-4xl sm:text-5xl">
                  {profileUser.name.charAt(0).toUpperCase()}
                </div>
              )}
            </div>

            {/* Profile Information */}
            <div className="flex-1 text-center md:text-left space-y-3 relative z-10">
              <div className="flex flex-wrap items-center justify-center md:justify-start gap-2.5">
                <h1 className="font-serif text-3xl sm:text-4xl tracking-tight leading-none m-0">{profileUser.name}</h1>
                {profileUser.verified && (
                  <span className="bg-accent/10 text-accent font-mono text-[9px] uppercase tracking-wider rounded-full px-2.5 py-0.5 inline-flex items-center gap-1 border border-accent/20">
                    <UserCheck size={9} /> Verified Maker
                  </span>
                )}
                <span className="font-mono text-[9px] uppercase tracking-wider border border-border-c rounded-full px-2 py-0.5 text-text-muted">
                  {profileUser.role.toUpperCase()}
                </span>
              </div>

              {profileUser.location && (
                <div className="font-mono text-xs text-text-muted flex items-center justify-center md:justify-start gap-1">
                  <MapPin size={12} className="text-accent" />
                  {profileUser.location}
                </div>
              )}

              {/* Developer stats */}
              {isSeller && (
                <div className="flex flex-wrap items-center justify-center md:justify-start gap-x-6 gap-y-2 mt-4 pt-4 border-t border-border-c/40 text-xs font-mono">
                  <div>
                    <span className="text-text-muted">Trust Score: </span>
                    <span className="text-text font-medium text-accent">{(profileUser.trustScore * 100).toFixed(0)}%</span>
                  </div>
                  <div>
                    <span className="text-text-muted">Active Listings: </span>
                    <span className="text-text font-medium">{listings.length}</span>
                  </div>
                  {isOwner && (
                    <div>
                      <span className="text-text-muted">AI Credits: </span>
                      <span className="text-text font-medium text-accent">{profileUser.aiPoints || 0} points</span>
                    </div>
                  )}
                </div>
              )}
            </div>
          </section>

          {displayMinimal ? (
            /* MINIMALIST PROFILE VIEW */
            <div className="max-w-xl mx-auto py-10 fade-in">
              <div className="bg-surface hairline rounded-2xl p-6 sm:p-8 space-y-6 text-center shadow-lg relative overflow-hidden">
                <div className="absolute top-0 inset-x-0 h-1 gold-gradient" />
                <div className="font-serif text-2xl font-medium">{profileUser.name}</div>
                <div className="font-mono text-xs text-text-muted uppercase tracking-widest">{profileUser.location || 'Boutique Maker'}</div>
                
                {profileUser.bio ? (
                  <p className="text-sm text-text-soft italic leading-relaxed px-4">
                    "{profileUser.bio}"
                  </p>
                ) : (
                  <p className="text-xs text-text-muted italic">No bio description provided.</p>
                )}
                
                <div className="pt-4 border-t border-border-c/60 flex items-center justify-center gap-6 text-xs font-mono">
                  <span className="flex items-center gap-1.5 text-text-muted">
                    <Activity size={12} className="text-accent" />
                    Active Catalog
                  </span>
                  <span className="font-medium">{listings.length} products</span>
                </div>
              </div>
            </div>
          ) : (
            /* DETAILED PORTFOLIO PROFILE VIEW */
            <div className="grid lg:grid-cols-3 gap-8 items-start">
              {/* Detailed bio / Info Card */}
              <div className="lg:col-span-1 space-y-6">
                <section className="bg-surface hairline rounded-2xl p-6 space-y-4">
                  <h3 className="font-serif text-xl border-b border-border-c/50 pb-2.5">About Maker</h3>
                  {profileUser.bio ? (
                    <p className="text-sm text-text-soft whitespace-pre-line leading-relaxed">
                      {profileUser.bio}
                    </p>
                  ) : (
                    <p className="text-xs text-text-muted italic">This developer hasn't drafted a biography yet.</p>
                  )}
                </section>

                {listings.length > 0 && (
                  <section className="bg-surface hairline rounded-2xl p-6 space-y-3 font-mono text-xs">
                    <h3 className="font-serif text-lg border-b border-border-c/50 pb-2.5 font-sans mb-3">Portfolio Stats</h3>
                    <div className="flex justify-between">
                      <span className="text-text-muted">Reputation:</span>
                      <span className="text-accent">Excellent</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-text-muted">Categories:</span>
                      <span>{Array.from(new Set(listings.map(l => l.category))).join(', ') || 'Various'}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-text-muted">Tech Stack:</span>
                      <span>Custom builds</span>
                    </div>
                  </section>
                )}
              </div>

              {/* Developer Listings */}
              <div className="lg:col-span-2 space-y-6">
                <h3 className="font-serif text-2xl">Published Creations</h3>
                
                {listings.length === 0 ? (
                  <div className="bg-surface hairline rounded-2xl p-10 text-center text-text-muted font-mono text-xs">
                    No active listings in the Vitrine catalog yet.
                  </div>
                ) : (
                  <div className="grid sm:grid-cols-2 gap-5">
                    {listings.map((item) => (
                      <article
                        key={item.id}
                        onClick={() => window.location.hash = `#/p/${item.slug}`}
                        className="group bg-surface hairline rounded-2xl overflow-hidden hover:border-accent transition-all duration-300 flex flex-col cursor-pointer hover:-translate-y-0.5"
                      >
                        {/* Cover Image */}
                        <div className="h-40 bg-surface-2 overflow-hidden relative border-b border-border-c">
                          {item.cover ? (
                            <img src={mediaUrl(item.cover)} alt={item.name} className="w-full h-full object-cover group-hover:scale-[1.02] transition-transform duration-500" />
                          ) : (
                            <div className="w-full h-full flex items-center justify-center bg-gradient-to-b from-surface to-surface-2 font-serif text-text-muted">
                              No Cover Photo
                            </div>
                          )}
                        </div>

                        {/* Details */}
                        <div className="p-4 flex-1 flex flex-col justify-between space-y-3">
                          <div>
                            <div className="font-serif text-lg group-hover:text-accent transition-colors truncate">{item.name}</div>
                            <p className="text-xs text-text-soft line-clamp-2 mt-1 min-h-[2rem] leading-relaxed">{item.tagline}</p>
                          </div>

                          <div className="flex items-center justify-between pt-2 border-t border-border-c/50 text-xs font-mono">
                            <span className="text-accent font-semibold">${item.price.toFixed(0)}</span>
                            <span className="text-text-muted uppercase text-[9px] tracking-wider bg-surface-2 px-2 py-0.5 rounded-full">{item.category}</span>
                          </div>
                        </div>
                      </article>
                    ))}
                  </div>
                )}
              </div>
            </div>
          )}
        </div>
      ) : (
        /* ==================== OWNER SETTINGS & BILLING ==================== */
        <div className="bg-surface hairline rounded-3xl overflow-hidden grid md:grid-cols-4 min-h-[500px] fade-in">
          {/* Side Menu */}
          <nav className="md:col-span-1 border-r border-border-c bg-surface/50 p-4 space-y-1">
            <div className="px-3 py-2 font-mono text-[9px] uppercase tracking-wider text-text-muted">My Account</div>
            {[
              { id: 'profile', label: 'Edit Profile', icon: UserIcon },
              { id: 'security', label: 'Login & Security', icon: Lock },
              { id: 'preferences', label: 'Preferences', icon: Palette },
              { id: 'ai', label: 'AI Credits & Limits', icon: Coins },
              { id: 'billing', label: 'Billing & Plans', icon: CreditCard }
            ].map((sec) => {
              const Icon = sec.icon;
              return (
                <button
                  key={sec.id}
                  onClick={() => setSettingsSection(sec.id as any)}
                  className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-xl text-xs font-mono text-left transition-colors ${
                    settingsSection === sec.id ? 'bg-accent/15 text-accent font-semibold' : 'text-text-soft hover:bg-surface-2'
                  }`}
                >
                  <Icon size={14} className={settingsSection === sec.id ? 'text-accent' : 'text-text-muted'} />
                  {sec.label}
                </button>
              );
            })}
          </nav>

          {/* Form Content */}
          <div className="md:col-span-3 p-6 sm:p-8 md:p-10 bg-surface">
            
            {/* EDIT PROFILE SECTION */}
            {settingsSection === 'profile' && (
              <form onSubmit={handleSaveProfile} className="space-y-6 fade-in">
                <div>
                  <h2 className="font-serif text-2xl">Edit Profile Details</h2>
                  <p className="text-text-muted text-xs font-mono mt-1">Configure your public-facing creator profile card</p>
                </div>

                {/* Avatar Photo Uploader */}
                <div className="flex flex-col sm:flex-row items-center gap-5 pt-3">
                  <div className="relative w-20 h-20 rounded-xl overflow-hidden bg-surface-2 hairline shrink-0">
                    {avatarUrl ? (
                      <img src={mediaUrl(avatarUrl)} alt="Avatar Preview" className="w-full h-full object-cover" />
                    ) : (
                      <div className="w-full h-full flex items-center justify-center text-text-muted font-serif text-2xl bg-accent-soft/20">
                        {displayName.charAt(0).toUpperCase() || '?'}
                      </div>
                    )}
                  </div>
                  <div className="space-y-1.5 text-center sm:text-left">
                    <label className="relative cursor-pointer inline-flex items-center gap-1.5 px-4 h-9 rounded-xl border border-border-c hover:border-accent transition-colors bg-surface text-xs font-mono font-medium">
                      <Upload size={12} />
                      {uploading ? 'Uploading...' : 'Upload Picture'}
                      <input type="file" accept="image/*" className="hidden" onChange={handleAvatarUpload} disabled={uploading} />
                    </label>
                    <p className="text-[10px] text-text-muted font-mono">JPG, PNG, WEBP (Max 2MB)</p>
                  </div>
                </div>

                <div className="grid sm:grid-cols-2 gap-4">
                  <div className="space-y-1.5">
                    <label className="text-xs font-mono text-text-muted">Display Name</label>
                    <input
                      type="text"
                      value={displayName}
                      onChange={(e) => setDisplayName(e.target.value)}
                      className="w-full px-3 py-2 rounded-xl border border-border-c bg-surface-2 text-sm focus:border-accent outline-none"
                      required
                    />
                  </div>
                  <div className="space-y-1.5">
                    <label className="text-xs font-mono text-text-muted">Location / Region</label>
                    <input
                      type="text"
                      value={location}
                      onChange={(e) => setLocation(e.target.value)}
                      placeholder="e.g. San Francisco, CA"
                      className="w-full px-3 py-2 rounded-xl border border-border-c bg-surface-2 text-sm focus:border-accent outline-none"
                    />
                  </div>
                </div>

                <div className="space-y-1.5">
                  <label className="text-xs font-mono text-text-muted">Biography</label>
                  <textarea
                    value={bio}
                    onChange={(e) => setBio(e.target.value)}
                    rows={4}
                    placeholder="Describe your design methodologies, stack specialties, or past products..."
                    className="w-full px-3 py-2 rounded-xl border border-border-c bg-surface-2 text-sm focus:border-accent outline-none resize-none leading-relaxed"
                  />
                </div>

                {isSeller && (
                  <div className="p-4 rounded-2xl hairline bg-surface-2/40 space-y-3">
                    <div className="flex items-center justify-between">
                      <div>
                        <div className="text-xs font-semibold font-mono">Minimalistic Profile View</div>
                        <div className="text-[10px] text-text-muted leading-tight mt-0.5">Toggle to hide detailed portfolio listings and display only a sleek contact card.</div>
                      </div>
                      <label className="relative inline-flex items-center cursor-pointer">
                        <input
                          type="checkbox"
                          checked={minimalProfile}
                          onChange={(e) => setMinimalProfile(e.target.checked)}
                          className="sr-only peer"
                        />
                        <div className="w-9 h-5 bg-border-c peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:height-4 after:h-4 after:w-4 after:transition-all peer-checked:bg-accent"></div>
                      </label>
                    </div>
                  </div>
                )}

                <div className="pt-4 flex items-center gap-3">
                  <button
                    type="submit"
                    disabled={profileSaving}
                    className="px-6 h-10 rounded-xl bg-text text-bg hover:opacity-90 transition-opacity text-xs font-mono font-medium disabled:opacity-50"
                  >
                    {profileSaving ? 'Saving Changes...' : 'Save Profile'}
                  </button>
                  {profileSuccess && (
                    <span className="text-success text-xs font-mono flex items-center gap-1">
                      <Check size={14} /> Profile updated successfully!
                    </span>
                  )}
                </div>
              </form>
            )}

            {/* SECURITY SECTION */}
            {settingsSection === 'security' && (
              <form onSubmit={handleChangePassword} className="space-y-6 fade-in">
                <div>
                  <h2 className="font-serif text-2xl">Login & Security</h2>
                  <p className="text-text-muted text-xs font-mono mt-1">Change your password or verify current security configurations</p>
                </div>

                {passwordError && (
                  <div className="p-3 bg-danger/10 border border-danger/20 rounded-xl text-danger text-xs font-mono flex items-center gap-2">
                    <AlertCircle size={14} />
                    {passwordError}
                  </div>
                )}

                {passwordSuccess && (
                  <div className="p-3 bg-success/10 border border-success/20 rounded-xl text-success text-xs font-mono flex items-center gap-2">
                    <Check size={14} />
                    Password updated successfully.
                  </div>
                )}

                <div className="space-y-1.5">
                  <label className="text-xs font-mono text-text-muted">Current Password</label>
                  <input
                    type="password"
                    value={currentPassword}
                    onChange={(e) => setCurrentPassword(e.target.value)}
                    className="w-full max-w-md px-3 py-2 rounded-xl border border-border-c bg-surface-2 text-sm focus:border-accent outline-none"
                    required
                  />
                </div>

                <div className="grid sm:grid-cols-2 gap-4 max-w-md">
                  <div className="space-y-1.5">
                    <label className="text-xs font-mono text-text-muted">New Password</label>
                    <input
                      type="password"
                      value={newPassword}
                      onChange={(e) => setNewPassword(e.target.value)}
                      className="w-full px-3 py-2 rounded-xl border border-border-c bg-surface-2 text-sm focus:border-accent outline-none"
                      required
                    />
                  </div>
                  <div className="space-y-1.5">
                    <label className="text-xs font-mono text-text-muted">Confirm New Password</label>
                    <input
                      type="password"
                      value={confirmPassword}
                      onChange={(e) => setConfirmPassword(e.target.value)}
                      className="w-full px-3 py-2 rounded-xl border border-border-c bg-surface-2 text-sm focus:border-accent outline-none"
                      required
                    />
                  </div>
                </div>

                <div className="pt-4">
                  <button
                    type="submit"
                    disabled={passwordSaving}
                    className="px-6 h-10 rounded-xl bg-text text-bg hover:opacity-90 transition-opacity text-xs font-mono font-medium disabled:opacity-50"
                  >
                    {passwordSaving ? 'Updating...' : 'Update Password'}
                  </button>
                </div>
              </form>
            )}

            {/* PREFERENCES SECTION */}
            {settingsSection === 'preferences' && (
              <div className="space-y-6 fade-in">
                <div>
                  <h2 className="font-serif text-2xl">Preferences</h2>
                  <p className="text-text-muted text-xs font-mono mt-1">Configure layout preferences and display colors</p>
                </div>

                <div className="space-y-4 pt-2">
                  <div className="space-y-2">
                    <label className="text-xs font-mono text-text-muted block">Theme Default</label>
                    <div className="grid grid-cols-2 gap-4 max-w-md">
                      <button
                        type="button"
                        onClick={() => {
                          setThemeDefault('dark');
                          document.documentElement.classList.add('dark');
                          api.updateProfile({ theme_default: 'dark' }).then(updateUser);
                        }}
                        className={`h-20 rounded-2xl border flex flex-col items-center justify-center gap-1.5 transition-colors ${
                          themeDefault === 'dark' ? 'border-accent bg-accent/5 font-semibold text-accent' : 'border-border-c hover:border-text-soft bg-surface-2'
                        }`}
                      >
                        <div className="w-5 h-5 rounded-full bg-slate-900 border border-slate-700" />
                        <span className="text-xs font-mono">Dark Edition</span>
                      </button>

                      <button
                        type="button"
                        onClick={() => {
                          setThemeDefault('light');
                          document.documentElement.classList.remove('dark');
                          api.updateProfile({ theme_default: 'light' }).then(updateUser);
                        }}
                        className={`h-20 rounded-2xl border flex flex-col items-center justify-center gap-1.5 transition-colors ${
                          themeDefault === 'light' ? 'border-accent bg-accent/5 font-semibold text-accent' : 'border-border-c hover:border-text-soft bg-surface-2'
                        }`}
                      >
                        <div className="w-5 h-5 rounded-full bg-slate-100 border border-slate-350" />
                        <span className="text-xs font-mono">Paper Light</span>
                      </button>
                    </div>
                  </div>
                </div>
              </div>
            )}

            {/* AI POINTS SECTION */}
            {settingsSection === 'ai' && (
              <div className="space-y-6 fade-in">
                <div>
                  <h2 className="font-serif text-2xl">AI Agentic Usage</h2>
                  <p className="text-text-muted text-xs font-mono mt-1">Monitor your point limits and configure AI integrations</p>
                </div>

                {/* Point Balance Metric */}
                <div className="p-6 rounded-2xl bg-surface-2 border border-border-c grid sm:grid-cols-3 gap-6 items-center">
                  <div className="sm:col-span-2 space-y-1.5">
                    <div className="text-xs font-mono text-text-muted">Available AI points</div>
                    <div className="font-serif text-4xl font-semibold text-accent">{profileUser.aiPoints || 0} Points</div>
                    <p className="text-[10px] text-text-muted font-mono leading-relaxed pt-1.5">
                      Points are automatically deducted when you request services from our agent fleet:
                      Concierge search queries, Buyer negotiations, and Custom cost quotes.
                    </p>
                  </div>
                  <div className="sm:col-span-1 bg-surface border border-border-c p-4 rounded-xl text-center space-y-1">
                    <Coins className="text-accent mx-auto" size={20} />
                    <div className="text-[10px] font-mono text-text-muted uppercase tracking-wider">Earn Points</div>
                    <div className="text-xs font-semibold font-serif">Buy any product</div>
                    <p className="text-[9px] text-text-muted font-mono leading-none mt-1">Get 10 points per dollar spent!</p>
                  </div>
                </div>

                {/* Fee structure list */}
                <div className="space-y-3 pt-2">
                  <h3 className="text-xs font-mono uppercase tracking-wider text-text-muted">Fee Schedule</h3>
                  <div className="divide-y divide-border-c/60">
                    <div className="py-2.5 flex items-center justify-between text-xs font-mono">
                      <span className="text-text-soft">AI Buyer Concierge query</span>
                      <span className="text-danger font-medium">-5 points</span>
                    </div>
                    <div className="py-2.5 flex items-center justify-between text-xs font-mono">
                      <span className="text-text-soft">Buyer Representative Bargain response</span>
                      <span className="text-danger font-medium">-10 points</span>
                    </div>
                    <div className="py-2.5 flex items-center justify-between text-xs font-mono">
                      <span className="text-text-soft">AI Feature Cost Estimator quote</span>
                      <span className="text-danger font-medium">-15 points</span>
                    </div>
                    <div className="py-2.5 flex items-center justify-between text-xs font-mono">
                      <span className="text-text-soft">Normal Search queries</span>
                      <span className="text-success font-medium">Free (0 points)</span>
                    </div>
                  </div>
                </div>

                {/* Alert Warning for empty points */}
                {(profileUser.aiPoints || 0) < 15 && (
                  <div className="p-4 bg-danger/10 border border-danger/20 rounded-xl text-xs font-mono text-danger flex items-start gap-2.5">
                    <AlertCircle size={16} className="shrink-0 mt-0.5" />
                    <div>
                      <div className="font-semibold">Low Points Balance</div>
                      <p className="text-[10px] text-danger/80 leading-normal mt-1">
                        You have less than 15 points. You might run out of points for estimating customized products. Make a purchase or buy standard files to replenish your wallet.
                      </p>
                    </div>
                  </div>
                )}
              </div>
            )}

            {/* BILLING & SUBSCRIPTIONS SECTION */}
            {settingsSection === 'billing' && (
              <div className="space-y-8 fade-in">
                <div>
                  <h2 className="font-serif text-2xl">Billing & Plans</h2>
                  <p className="text-text-muted text-xs font-mono mt-1">Change developer tiers, view subscriptions, or check receipt archives</p>
                </div>

                {/* Developer Tier Configuration */}
                {isSeller ? (
                  <div className="space-y-4">
                    <h3 className="text-xs font-mono uppercase tracking-wider text-text-muted">Current Listing Plan</h3>
                    
                    <div className="grid sm:grid-cols-3 gap-4">
                      {['free', 'studio', 'atelier'].map((tierName) => {
                        const tier = PLAN_DETAILS[tierName as SellerPlan];
                        const active = profileUser.plan === tierName;
                        return (
                          <div
                            key={tierName}
                            className={`p-4 rounded-xl border flex flex-col justify-between ${
                              active ? 'border-accent bg-accent/5 shadow-sm' : 'border-border-c'
                            }`}
                          >
                            <div>
                              <div className="font-serif text-lg font-medium">{tier.name}</div>
                              <div className="font-mono text-[10px] text-text-muted mt-1">${tier.price}/month</div>
                              <ul className="text-[10px] font-mono text-text-soft space-y-1 mt-3">
                                <li>• {tier.posts === 'unlimited' ? 'Unlimited' : tier.posts} posts</li>
                                <li>• {tier.commission}% commission</li>
                              </ul>
                            </div>
                            <button
                              type="button"
                              onClick={() => handlePlanChange(tierName as SellerPlan)}
                              disabled={active}
                              className={`w-full mt-4 h-8 rounded-lg text-xs font-mono font-medium transition-colors ${
                                active ? 'bg-text text-bg cursor-default' : 'hairline hover:border-accent'
                              }`}
                            >
                              {active ? 'Active Plan' : 'Select'}
                            </button>
                          </div>
                        );
                      })}
                    </div>
                  </div>
                ) : (
                  <div className="p-4 rounded-2xl bg-surface-2/65 hairline text-xs font-mono space-y-1">
                    <div className="font-semibold text-text">Standard Buyer Account</div>
                    <p className="text-text-muted text-[10px]">
                      Buyers do not pay subscription fees. Enjoy browsing creation files, checking out with escrow security, and chatting with creators.
                    </p>
                  </div>
                )}

                {/* Payment method */}
                <div className="space-y-3">
                  <h3 className="text-xs font-mono uppercase tracking-wider text-text-muted">Payment Wallet</h3>
                  <div className="p-4 rounded-xl hairline flex items-center justify-between">
                    <div className="flex items-center gap-3">
                      <div className="bg-surface-2 px-2.5 py-1.5 rounded-lg border border-border-c text-[10px] font-mono font-bold uppercase tracking-wider">Visa</div>
                      <div>
                        <div className="text-xs font-semibold font-mono">•••• •••• •••• 4242</div>
                        <div className="text-[10px] text-text-muted font-mono">Expires 12/2028</div>
                      </div>
                    </div>
                    <button type="button" className="text-xs font-mono text-accent hover:underline">Edit</button>
                  </div>
                </div>

                {/* Invoices List */}
                <div className="space-y-4">
                  <h3 className="text-xs font-mono uppercase tracking-wider text-text-muted">Invoices Archive</h3>
                  
                  {billingLoading ? (
                    <div className="text-xs font-mono text-text-muted">Loading invoice list...</div>
                  ) : !billingInfo?.invoices || billingInfo.invoices.length === 0 ? (
                    <div className="p-4 text-center rounded-xl bg-surface-2/40 border border-dashed border-border-c text-xs font-mono text-text-muted">
                      No invoices recorded yet.
                    </div>
                  ) : (
                    <div className="overflow-hidden border border-border-c rounded-xl divide-y divide-border-c/70">
                      {billingInfo.invoices.map((inv: any) => (
                        <div key={inv.id} className="p-3 sm:p-4 flex items-center justify-between text-xs font-mono">
                          <div>
                            <div className="font-semibold">{inv.description}</div>
                            <div className="text-[10px] text-text-muted mt-1">{inv.date} · {inv.id}</div>
                          </div>
                          <div className="flex items-center gap-3">
                            <span className="font-semibold text-text">${inv.amount.toFixed(2)}</span>
                            <span className="text-[9px] uppercase font-semibold text-success bg-success/15 px-2 py-0.5 rounded-full border border-success/25">Paid</span>
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>

              </div>
            )}

          </div>
        </div>
      )}

      {/* TOLERABLE USER ADVERTISEMENT PLACEMENT */}
      {showAds && (
        <section className="mt-14 max-w-3xl mx-auto text-center fade-in">
          <div className="p-5 rounded-2xl hairline bg-surface/40 relative overflow-hidden flex flex-col sm:flex-row items-center justify-between gap-4">
            <div className="font-mono text-[8px] uppercase tracking-widest text-text-muted absolute top-2 right-3">Sponsored</div>
            <div className="flex items-center gap-3 text-left">
              <div className="w-10 h-10 rounded-lg bg-accent/25 border border-accent/20 flex items-center justify-center text-accent shrink-0">
                <Crown size={16} />
              </div>
              <div>
                <div className="font-serif text-sm font-medium">Deploy your creations instantly with Vitrine hosting</div>
                <p className="text-[10px] text-text-soft font-mono leading-normal mt-0.5">Get 30 days of free atelier server container deployment.</p>
              </div>
            </div>
            <a href="#/pricing" className="shrink-0 inline-flex items-center gap-1 bg-accent hover:bg-accent-soft text-[var(--accent-ink)] font-mono text-[10px] uppercase tracking-wider rounded-xl px-4 py-2 font-medium transition-colors">
              Upgrade Plan <ChevronRight size={10} />
            </a>
          </div>
        </section>
      )}
    </main>
  );
}
