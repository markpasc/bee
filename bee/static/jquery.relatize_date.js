// Almost all credit goes to Rick Olson.
(function($) {
  $.fn.relatizeDate = function(params) {
    if(typeof $.relatizeDate.language == "undefined")
      if(typeof params == "undefined")
        for(key in $relatizeDateTranslation)
          var language = key;
      else if(typeof params.availableLanguages == "object") {
        var currentLanguage = (typeof navigator.browserLanguage == "undefined") ? 
          navigator.language : navigator.browserLanguage;
        currentLanguage.toLowerCase().match(/((\w+)-\w+)/);
        if($relatizeDateTranslation[RegExp.$1])
          var language = RegExp.$1;
        else if(RegExp.$1 != RegExp.$2 && $relatizeDateTranslation[RegExp.$2])
          var language = RegExp.$2;
        else
          var language = params.defaultLanguage;
      } else
        var language = params.defaultLanguage;
    
    $.relatizeDate.translation = $relatizeDateTranslation[language];
    if (typeof $.relatizeDate.translation.default_date_fmt != "undefined") dfmt = $.relatizeDate.translation.default_date_fmt;
    else dfmt = '%B %d, %Y %I:%M %p';
    return $(this).each(function() {
      if (typeof params.titleize != "undefined" && params.titleize == true)
	  $(this).attr('title', $.relatizeDate.strftime(new Date($(this).text()), dfmt));
      $(this).text($.relatizeDate(this));
    });
  };

  $.relatizeDate = function(element) {
    return $.relatizeDate.timeAgoInWords(new Date($(element).text()));
  };

  $.extend($.relatizeDate, {
    /**
     * Given a formatted string, replace the necessary items and return.
     * Example: Time.now().strftime("%B %d, %Y") => February 11, 2008
     * @param {String} format The formatted string used to format the results
     */
    strftime: function(date, format) {
      var day = date.getDay(), month = date.getMonth(),
      hours = date.getHours(), minutes = date.getMinutes(),
      translation = $.relatizeDate.translation;

      function pad(num) { 
        var string = num.toString(10);
        return new Array((2 - string.length) + 1).join('0') + string;
      };

      return format.replace(/\%([aAbBcdHImMpSwyY])/g, function(part) {
        switch(part[1]) {
          case 'a': return translation.shortDays[day]; break;
          case 'A': return translation.days[day]; break;
          case 'b': return translation.shortMonths[month]; break;
          case 'B': return translation.months[month]; break;
          case 'c': return date.toString(); break;
          case 'd': return pad(date.getDate()); break;
          case 'H': return pad(hours); break;
          case 'I': return pad((hours + 12) % 12); break;
          case 'm': return pad(month + 1); break;
          case 'M': return pad(minutes); break;
          case 'p': return hours > 12 ? 'PM' : 'AM'; break;
          case 'S': return pad(date.getSeconds()); break;
          case 'w': return day; break;
          case 'y': return pad(date.getFullYear() % 100); break;
          case 'Y': return date.getFullYear().toString(); break;
        }
      });
    },
  
    timeAgoInWords: function(targetDate, includeTime) {
      return $.relatizeDate.distanceOfTimeInWords(targetDate, new Date(), includeTime);
    },
  
    /**
     * Return the distance of time in words between two Date's
     * Example: '5 days ago', 'about an hour ago'
     * @param {Date} fromTime The start date to use in the calculation
     * @param {Date} toTime The end date to use in the calculation
     * @param {Boolean} Include the time in the output
     */
    distanceOfTimeInWords: function(fromTime, toTime, includeTime) {
      var delta = parseInt((toTime.getTime() - fromTime.getTime()) / 1000, 10);
      var translation = $.relatizeDate.translation;
      if (delta < 60) {
          return translation.ltm; // (L)ess (T)han a (M)inute
      } else if (delta < 120) {
          return translation.abm; // (AB)out a (M)inute
      } else if (delta < (45*60)) {
          return translation.m.replace("%d", parseInt(delta / 60, 10)); // (M)inute
      } else if (delta < (120*60)) {
          return translation.h; // (H)our
      } else if (delta < (24*60*60)) {
          return translation.abh.replace("%d", parseInt(delta / 3600, 10)); // (AB)out a (H)our
      } else if (delta < (48*60*60)) {
        if (typeof translation.default_time_fmt != 'undefined' && translation.default_time_fmt == 12) time = (fromTime.getHours() + 12) % 12 + ':' + fromTime.getMinutes() + ' ' + (fromTime.getHours() > 12 ? 'PM' : 'AM');
        else time = fromTime.getHours() + ':' + fromTime.getMinutes();
          return translation.d + ' ' + translation.at + ' ' + time; // yester(D)ay
      } else {
        var days = (parseInt(delta / 86400, 10)).toString();
        if (days > 5) {
          var fmt  = '%B %d, %Y';
          if (includeTime) fmt += ' %I:%M %p';
          return $.relatizeDate.strftime(fromTime, fmt);
        } else
          if (typeof(translation.shortds) != 'undefined' &&
	      typeof(translation.shortds[days-2]) != 'undefined')
	      return translation.shortds[days-2]; // less than 5 days
          else return translation.ds.replace("%d", days); // (D)ay(S)
      }
    }
  });
})(jQuery);
