// Zero results state — strict messaging, no suggestions
export default function EmptyState() {
    return (
        <div className="empty-state" role="status" aria-live="polite" data-testid="empty-state">
            <div className="empty-icon" aria-hidden="true">🔍</div>
            <h3>No Restaurants Found</h3>
            <p>No restaurants found matching your preferences.</p>
        </div>
    );
}
