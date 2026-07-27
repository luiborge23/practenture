#!/bin/bash
# DNS propagation verification and iOS config update script

echo "Checking DNS propagation for api.practenture.com..."

# Check if DNS has propagated
for i in {1..12}; do
    echo "Attempt $i: Checking DNS..."
    
    if dig +short api.practenture.com A 2>/dev/null | grep -q "3.85.35.73"; then
        echo "✅ DNS propagated! IP: $(dig +short api.practenture.com A)"
        echo ""
        
        # Update iOS Info.plist
        echo "Updating iOS backend URL..."
        plist_path="/Users/luisborges/2026/Practenture-ios/Practenture/Info.plist"
        
        if [ -f "$plist_path" ]; then
            # Backup first
            cp "$plist_path" "${plist_path}.bak"
            
            # Replace backend URL with HTTPS
            sed -i '' 's|<string>http://3.85.35.73</string>|<string>https://api.practenture.com</string>|g' "$plist_path"
            
            echo "✅ iOS config updated!"
            echo ""
            echo "New backend URL:"
            grep "PRACTENTURE_BACKEND_URL" "$plist_path"
            
            echo ""
            echo "Next steps:"
            echo "1. Rebuild iOS app in Xcode"
            echo "2. Test with https://api.practenture.com"
            
            # Clean build cache
            echo ""
            echo "Running clean build..."
            cd /Users/luisborges/2026/Practenture-ios/Practenture
            xcodebuild -project Practenture.xcodeproj -scheme Practenture -configuration Debug clean build 2>&1 | tail -5
            
            exit 0
        else
            echo "❌ Info.plist not found at $plist_path"
            exit 1
        fi
    fi
    
    echo "DNS not yet propagated. Waiting 30 seconds..."
    sleep 30
done

echo "❌ DNS propagation check timed out after 6 minutes"
echo "Please manually check: dig +short api.practenture.com A"
