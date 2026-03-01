// Individual result card — displays one LLM-ranked restaurant
export default function ResultCard({ restaurant }) {
    const {
        rank, name, cuisine, restaurant_type, rating,
        avg_cost_for_two, city, online_ordering, table_booking,
        zomato_url, phone, llm_blurb,
    } = restaurant;

    const hasOnline = online_ordering === 'yes';
    const hasBooking = table_booking === 'yes';

    return (
        <article className="result-card" data-testid="result-card" aria-label={`Rank ${rank}: ${name}`}>
            <div className="card-rank-ribbon">#{rank} Pick</div>

            <div className="card-body">
                <h3 className="card-name">{name}</h3>

                <div className="card-tags">
                    {cuisine && cuisine !== 'N/A' && (
                        <span className="tag">{cuisine}</span>
                    )}
                    {restaurant_type && restaurant_type !== 'N/A' && (
                        <span className="tag type-tag">{restaurant_type}</span>
                    )}
                </div>

                <div className="card-meta">
                    {rating != null && (
                        <span className="meta-rating">
                            <span className="star-icon">★</span>
                            {Number(rating).toFixed(1)}
                        </span>
                    )}
                    {avg_cost_for_two != null && (
                        <span className="meta-cost">₹{avg_cost_for_two} for two</span>
                    )}
                    {city && city !== 'N/A' && (
                        <span className="meta-city">📍 {city}</span>
                    )}
                </div>

                <div className="card-badges">
                    <span className={`badge ${hasOnline ? 'online' : 'offline'}`}>
                        {hasOnline ? '🛵 Online Order' : '🚫 No Online Order'}
                    </span>
                    <span className={`badge ${hasBooking ? 'booking' : 'no-booking'}`}>
                        {hasBooking ? '📅 Table Booking' : 'Walk-in Only'}
                    </span>
                </div>

                {llm_blurb && (
                    <blockquote className="card-blurb">
                        &ldquo;{llm_blurb}&rdquo;
                    </blockquote>
                )}

                <div className="card-footer">
                    {phone && phone !== 'N/A' && (
                        <span className="card-phone">📞 {phone}</span>
                    )}
                    {zomato_url && zomato_url !== 'N/A' && (
                        <a
                            className="zomato-link"
                            href={zomato_url}
                            target="_blank"
                            rel="noopener noreferrer"
                            aria-label={`View ${name} on Zomato`}
                            id={`zomato-link-${rank}`}
                        >
                            View on Zomato ↗
                        </a>
                    )}
                </div>
            </div>
        </article>
    );
}
