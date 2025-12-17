// src/ui/Card.jsx

/**
 * Card component for consistent panel styling.
 * 
 * @param {string} variant - 'default' | 'elevated' | 'outlined'
 * @param {string} statusColor - Optional border accent color for status indication
 * @param {boolean} hover - Whether to show hover effect
 */
function Card({
    children,
    variant = 'default',
    statusColor = null,
    hover = false,
    className = '',
    ...props
}) {
    const classes = [
        'card',
        `card--${variant}`,
        hover ? 'card--hover' : '',
        className,
    ].filter(Boolean).join(' ');

    const style = statusColor ? { '--card-status-color': statusColor } : {};

    return (
        <div className={classes} style={style} {...props}>
            {children}
        </div>
    );
}

/**
 * Card header with title and optional actions
 */
function CardHeader({ children, title, actions, className = '' }) {
    return (
        <div className={`card-header ${className}`}>
            {title && <h3 className="card-title">{title}</h3>}
            {children}
            {actions && <div className="card-actions">{actions}</div>}
        </div>
    );
}

/**
 * Card body for main content
 */
function CardBody({ children, className = '' }) {
    return (
        <div className={`card-body ${className}`}>
            {children}
        </div>
    );
}

Card.Header = CardHeader;
Card.Body = CardBody;

export default Card;
