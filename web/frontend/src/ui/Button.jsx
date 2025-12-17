// src/ui/Button.jsx

/**
 * Button component with multiple variants.
 * 
 * @param {string} variant - 'primary' | 'secondary' | 'danger' | 'ghost'
 * @param {string} size - 'sm' | 'md' | 'lg'
 * @param {boolean} fullWidth - Whether button takes full width
 * @param {boolean} loading - Show loading state
 */
function Button({
    children,
    variant = 'primary',
    size = 'md',
    fullWidth = false,
    loading = false,
    disabled = false,
    className = '',
    ...props
}) {
    const classes = [
        'btn',
        `btn--${variant}`,
        `btn--${size}`,
        fullWidth ? 'btn--full' : '',
        loading ? 'btn--loading' : '',
        className,
    ].filter(Boolean).join(' ');

    return (
        <button
            className={classes}
            disabled={disabled || loading}
            {...props}
        >
            {loading && <span className="btn-spinner" />}
            <span className="btn-content">{children}</span>
        </button>
    );
}

export default Button;
