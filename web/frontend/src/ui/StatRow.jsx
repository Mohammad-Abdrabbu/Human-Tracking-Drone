// src/ui/StatRow.jsx

/**
 * Stat display component for key-value pairs.
 * 
 * @param {string} label - The label text
 * @param {string} value - The value to display
 * @param {string} variant - 'default' | 'compact' | 'large'
 * @param {string} valueColor - Optional color for the value text
 */
function StatRow({
    label,
    value,
    variant = 'default',
    valueColor = null,
    className = ''
}) {
    const classes = [
        'stat-row',
        `stat-row--${variant}`,
        className,
    ].filter(Boolean).join(' ');

    const valueStyle = valueColor ? { color: valueColor } : {};

    return (
        <div className={classes}>
            <span className="stat-label">{label}</span>
            <span className="stat-value" style={valueStyle}>{value}</span>
        </div>
    );
}

/**
 * Large stat card with label and prominent value
 */
function StatCard({
    label,
    value,
    icon = null,
    statusColor = null,
    className = ''
}) {
    const classes = ['stat-card', className].filter(Boolean).join(' ');
    const style = statusColor ? { '--stat-status-color': statusColor } : {};

    return (
        <div className={classes} style={style}>
            {icon && <span className="stat-card-icon">{icon}</span>}
            <span className="stat-card-label">{label}</span>
            <span className="stat-card-value">{value}</span>
        </div>
    );
}

StatRow.Card = StatCard;

export default StatRow;
