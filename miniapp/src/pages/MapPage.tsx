import React, { useEffect, useRef, useState } from "react";
import L from "leaflet";
import { api } from "../api/client";
import type { MiniAppMapProperty } from "../types/miniapp";
import {
  formatPropertyPrice,
  getDealTypeLabel,
  getMapTileConfig,
  getPropertyTypeLabel,
  isValidCoordinate,
} from "../utils/format";
import { triggerHaptic } from "../telegram/webapp";

interface MapPageProps {
  onSelectProperty: (id: number) => void;
}

const DEFAULT_CENTER: [number, number] = [41.2995, 69.2401]; // Tashkent
const DEFAULT_ZOOM = 12;

export const MapPage: React.FC<MapPageProps> = ({ onSelectProperty }) => {
  const mapContainerRef = useRef<HTMLDivElement | null>(null);
  const mapInstanceRef = useRef<L.Map | null>(null);
  const markersRef = useRef<L.Marker[]>([]);

  const [properties, setProperties] = useState<MiniAppMapProperty[]>([]);
  const [selectedProperty, setSelectedProperty] = useState<MiniAppMapProperty | null>(null);
  const [loading, setLoading] = useState<boolean>(true);

  // Initialize Leaflet map
  useEffect(() => {
    if (!mapContainerRef.current || mapInstanceRef.current) return;

    const map = L.map(mapContainerRef.current, {
      center: DEFAULT_CENTER,
      zoom: DEFAULT_ZOOM,
      zoomControl: false,
    });

    // Add Tile layer with valid attribution and configurable/default OSM tile source
    const { url: tileUrl, attribution: tileAttr } = getMapTileConfig();
    L.tileLayer(tileUrl, {
      attribution: tileAttr,
      maxZoom: 19,
    }).addTo(map);

    // Zoom control at top-left
    L.control.zoom({ position: "topleft" }).addTo(map);

    mapInstanceRef.current = map;

    return () => {
      map.remove();
      mapInstanceRef.current = null;
    };
  }, []);

  // Fetch properties with coordinates
  useEffect(() => {
    let isMounted = true;
    setLoading(true);

    api
      .getMapProperties()
      .then((items) => {
        if (!isMounted) return;
        setProperties(items);
      })
      .catch(() => {
        // Handle error silently or set empty
      })
      .finally(() => {
        if (isMounted) setLoading(false);
      });

    return () => {
      isMounted = false;
    };
  }, []);

  // Sync markers onto Leaflet map
  useEffect(() => {
    const map = mapInstanceRef.current;
    if (!map) return;

    // Clear existing markers
    markersRef.current.forEach((m) => m.remove());
    markersRef.current = [];

    const newMarkers: L.Marker[] = [];

    properties.forEach((prop) => {
      if (!isValidCoordinate(prop.latitude, prop.longitude)) {
        return;
      }

      const lat =
        typeof prop.latitude === "number"
          ? prop.latitude
          : parseFloat(String(prop.latitude));
      const lng =
        typeof prop.longitude === "number"
          ? prop.longitude
          : parseFloat(String(prop.longitude));

      const priceDisplay = formatPropertyPrice(prop.price, prop.currency);

      const icon = L.divIcon({
        className: "custom-leaflet-marker",
        html: `<div class="price-pill-marker" title="${priceDisplay}">${priceDisplay}</div>`,
        iconSize: [85, 26],
        iconAnchor: [42, 13],
      });

      const marker = L.marker([lat, lng], {
        icon,
        riseOnHover: true,
        zIndexOffset: 100,
      });

      marker.on("click", () => {
        triggerHaptic("selection");
        setSelectedProperty(prop);
      });

      marker.addTo(map);
      newMarkers.push(marker);
    });

    markersRef.current = newMarkers;

    // Fit bounds if markers exist
    if (newMarkers.length > 0) {
      const group = L.featureGroup(newMarkers);
      map.fitBounds(group.getBounds().pad(0.15), { maxZoom: 15 });
    }
  }, [properties]);

  // Geolocation locate me
  const handleLocateMe = () => {
    triggerHaptic("light");
    if (!navigator.geolocation || !mapInstanceRef.current) return;
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        const { latitude, longitude } = pos.coords;
        const map = mapInstanceRef.current;
        if (map) {
          map.setView([latitude, longitude], 15);
          L.circleMarker([latitude, longitude], {
            radius: 8,
            color: "#2563eb",
            fillColor: "#3b82f6",
            fillOpacity: 0.8,
          })
            .addTo(map)
            .bindPopup("Sizning joylashuvingiz")
            .openPopup();
        }
      },
      () => {
        // Geolocation denied or unavailable
      }
    );
  };

  const selectedPriceDisplay = selectedProperty
    ? formatPropertyPrice(selectedProperty.price, selectedProperty.currency)
    : "";

  return (
    <div className="map-container">
      <div id="leaflet-map" ref={mapContainerRef} />

      <button
        className="map-locate-btn"
        onClick={handleLocateMe}
        title="Mening joylashuvim"
        aria-label="Locate me"
      >
        🎯
      </button>

      {loading && (
        <div
          style={{
            position: "absolute",
            top: "16px",
            left: "50%",
            transform: "translateX(-50%)",
            zIndex: 1000,
            backgroundColor: "var(--card-bg)",
            padding: "6px 14px",
            borderRadius: "16px",
            fontSize: "12px",
            boxShadow: "0 2px 8px rgba(0,0,0,0.15)",
          }}
        >
          Xaritada uylar yuklanmoqda...
        </div>
      )}

      {selectedProperty && (
        <div className="map-floating-panel">
          <img
            src={
              selectedProperty.thumbnail_url ||
              "data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='60' height='60' fill='%23e5e7eb'><rect width='60' height='60'/><text x='50%' y='50%' dominant-baseline='middle' text-anchor='middle' fill='%239ca3af' font-size='11' font-family='sans-serif'>UyAI</text></svg>"
            }
            alt={selectedProperty.title}
            className="map-floating-cover"
            onError={(e) => {
              (e.target as HTMLImageElement).src =
                "data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='60' height='60' fill='%23e5e7eb'><rect width='60' height='60'/><text x='50%' y='50%' dominant-baseline='middle' text-anchor='middle' fill='%239ca3af' font-size='11' font-family='sans-serif'>UyAI</text></svg>";
            }}
          />
          <div className="map-floating-info">
            <div
              style={{
                fontSize: "15px",
                fontWeight: "800",
                color: "var(--text-color)",
              }}
            >
              {selectedPriceDisplay}
            </div>
            <div
              style={{
                fontSize: "13px",
                fontWeight: "600",
                whiteSpace: "nowrap",
                overflow: "hidden",
                textOverflow: "ellipsis",
              }}
            >
              {selectedProperty.title}
            </div>
            <div style={{ fontSize: "11px", color: "var(--hint-color)" }}>
              📍 {selectedProperty.district || "Toshkent"} •{" "}
              {getDealTypeLabel(selectedProperty.listing_type)} •{" "}
              {getPropertyTypeLabel(selectedProperty.property_type)}
            </div>
          </div>
          <button
            className="header-btn"
            style={{
              backgroundColor: "var(--btn-color)",
              color: "var(--btn-text-color)",
              padding: "8px 12px",
            }}
            onClick={() => onSelectProperty(selectedProperty.id)}
          >
            Ko‘rish
          </button>
        </div>
      )}
    </div>
  );
};
