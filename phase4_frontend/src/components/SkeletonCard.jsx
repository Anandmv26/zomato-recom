// Skeleton loading card — mimics result card shape
export default function SkeletonCard() {
    return (
        <div className="skeleton-card" role="status" aria-label="Loading restaurant">
            <div className="skeleton-line sk-title" />
            <div className="skeleton-line sk-tag" />
            <div className="skeleton-line sk-blurb" />
            <div className="skeleton-line sk-text" />
            <div className="skeleton-line sk-text2" />
        </div>
    );
}
