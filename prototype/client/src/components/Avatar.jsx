import { useEffect, useState } from 'react';

// Shows the user's profile photo, falling back to their initials whenever
// there is no photo set or the file fails to load. That fallback is what keeps
// the demo working on a fresh clone where no images have been dropped in yet.
export default function Avatar({ user, size = 'md', className = '' }) {
  const [failed, setFailed] = useState(false);

  // A different user (or a newly added photo) deserves a fresh attempt.
  useEffect(() => { setFailed(false); }, [user?.avatarUrl]);

  const sizeClass = size === 'md' ? '' : ` avatar-${size}`;
  const classes = `avatar${sizeClass}${className ? ' ' + className : ''}`;
  const showPhoto = user?.avatarUrl && !failed;

  return (
    <span className={classes} aria-hidden="true">
      {showPhoto ? (
        <img
          className="avatar-img"
          src={user.avatarUrl}
          alt=""
          onError={() => setFailed(true)}
        />
      ) : (
        user?.initials
      )}
    </span>
  );
}
