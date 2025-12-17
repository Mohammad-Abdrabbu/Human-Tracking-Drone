// src/ui/Badge.jsx

/**
 * Status badge component with multiple variants.
 * 
 * @param {string} variant - 'success' | 'warning' | 'error' | 'info' | 'neutral'
 * @param {string} size - 'sm' | 'md' | 'lg'
 * @param {boolean} pulse - Whether to show a pulsing animation
 * @param {string} className - Additional CSS classes
 */
function Badge({
    children,
    variant = 'neutral',
    size = 'md',
    pulse = false,
    className = ''
}) {
    const classes = [
        'badge',
        `badge--${variant}`,
        `badge--${size}`,
        pulse ? 'badge--pulse' : '',
        className,
    ].filter(Boolean).join(' ');

    return (
        <span className={classes}>
            {pulse && <span className="badge-dot" />}
            {children}
        </span>
    );
}

export default Badge;
