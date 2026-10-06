SELECT COUNT(*) FROM singer;	concert_singer
SELECT count(*) FROM singer;	concert_singer
SELECT Name, Country, Age FROM singer ORDER BY Age DESC;	concert_singer
SELECT Name, Country, Age FROM singer ORDER BY Age DESC;	concert_singer
SELECT avg(Age) , min(Age) , max(Age) FROM singer WHERE Country = 'France';	concert_singer
SELECT avg(Age) , min(Age) , max(Age) FROM singer WHERE Country = 'France';	concert_singer
SELECT Song_Name, Song_release_year FROM singer ORDER BY Age ASC LIMIT 1;	concert_singer
SELECT Song_Name, Song_release_year FROM singer WHERE Age = (SELECT MAX(Age) FROM singer);	concert_singer
SELECT DISTINCT Country FROM singer WHERE Age > 20;	concert_singer
SELECT DISTINCT Country FROM singer WHERE Age > 20;	concert_singer
SELECT Country, COUNT(*) FROM singer GROUP BY Country;	concert_singer
SELECT Country, COUNT(*) FROM singer GROUP BY Country;	concert_singer
SELECT Song_Name FROM singer WHERE Age > (SELECT AVG(Age) FROM singer)	concert_singer
SELECT Song_Name FROM singer WHERE Age > (SELECT AVG(Age) FROM singer)	concert_singer
SELECT Location, Name FROM stadium WHERE Capacity BETWEEN 5000 AND 10000;	concert_singer
SELECT Location, Name FROM stadium WHERE Capacity BETWEEN 5000 AND 10000;	concert_singer
SELECT MAX(capacity), AVG(capacity) FROM stadium;	concert_singer
SELECT avg(Capacity), max(Capacity) FROM stadium;	concert_singer
SELECT Name, Capacity FROM stadium ORDER BY Average DESC LIMIT 1;	concert_singer
SELECT Name, Capacity FROM stadium ORDER BY Average DESC LIMIT 1;	concert_singer
SELECT COUNT(*) FROM concert WHERE Year IN ('2014', '2015');	concert_singer
SELECT COUNT(*) FROM concert WHERE YEAR IN ('2014', '2015');	concert_singer
SELECT t1.Name, COUNT(t2.concert_ID) FROM stadium AS t1 JOIN concert AS t2 ON t1.Stadium_ID = t2.Stadium_ID GROUP BY t1.Stadium_ID;	concert_singer
SELECT t1.Name, COUNT(t2.concert_ID) FROM stadium AS t1 JOIN concert AS t2 ON t1.Stadium_ID = t2.Stadium_ID GROUP BY t1.Stadium_ID;	concert_singer
SELECT t1.name, t1.capacity FROM stadium AS t1 JOIN concert AS t2 ON t1.stadium_id = t2.stadium_id WHERE t2.year >=2014 GROUP BY t1.stadium_id ORDER BY COUNT(t2.concert_id) DESC LIMIT 1;	concert_singer
SELECT t1.name, t1.capacity FROM stadium AS t1 JOIN concert AS t2 ON t1.stadium_id = t2.stadium_id WHERE t2.year >2013 GROUP BY t1.stadium_id ORDER BY COUNT(*) DESC LIMIT 1;	concert_singer
SELECT Year FROM concert GROUP BY Year ORDER BY COUNT(*) DESC LIMIT 1;	concert_singer
SELECT Year FROM concert GROUP BY Year ORDER BY COUNT(*) DESC LIMIT 1;	concert_singer
SELECT Name FROM stadium WHERE Stadium_ID NOT IN (SELECT Stadium_ID FROM concert)	concert_singer
SELECT Name FROM stadium WHERE Stadium_ID NOT IN (SELECT Stadium_ID FROM concert);	concert_singer
SELECT Country FROM singer WHERE Age >40 INTERSECT SELECT Country FROM singer WHERE Age < 30;	concert_singer
SELECT Name FROM stadium WHERE Stadium_ID NOT IN (SELECT Stadium_ID FROM concert WHERE Year = '2014')	concert_singer
SELECT Name FROM stadium WHERE Stadium_ID NOT IN (SELECT Stadium_ID FROM concert WHERE Year = '2014')	concert_singer
SELECT c.concert_Name, c.Theme, COUNT(sic.Singer_ID) AS Number_of_Singers FROM concert c LEFT JOIN singer_in_concert sic ON c.concert_ID = sic.concert_ID GROUP BY c.concert_ID, c.concert_Name, c.Theme;	concert_singer
SELECT T3.concert_Name, T3.Theme, COUNT(T2.Singer_ID) FROM singer_in_concert AS T1 JOIN singer AS T2 ON T1.Singer_ID = T2.Singer_ID JOIN concert AS T3 ON T1.concert_ID = T3.concert_ID GROUP BY T3.concert_Name, T3.Theme;	concert_singer
SELECT T1.Name, COUNT(*) FROM singer AS T1 JOIN singer_in_concert AS T2 ON T1.Singer_ID = T2.Singer_ID GROUP BY T1.Singer_ID;	concert_singer
SELECT T1.Name, COUNT(T2.concert_ID) FROM singer AS T1 JOIN singer_in_concert AS T2 ON T1.Singer_ID = T2.Singer_ID GROUP BY T1.Name;	concert_singer
SELECT T2.Name FROM singer_in_concert AS T1 JOIN singer AS T2 ON T1.Singer_ID = T2.Singer_ID JOIN concert AS T3 ON T1.concert_ID = T3.concert_ID WHERE T3.Year = '2014';	concert_singer
SELECT T2.Name FROM singer_in_concert AS T1 JOIN singer AS T2 ON T1.Singer_ID = T2.Singer_ID JOIN concert AS T3 ON T1.concert_ID = T3.concert_ID WHERE T3.Year = '2014';	concert_singer
SELECT Name, Country FROM singer WHERE Song_Name LIKE '%Hey%';	concert_singer
SELECT T1.Name, T1.Country FROM singer AS T1 JOIN singer_in_concert AS T2 ON T1.Singer_ID = T2.Singer_ID WHERE T1.Song_Name LIKE '%Hey%';	concert_singer
SELECT s.Name, s.Location FROM stadium s JOIN concert c ON s.Stadium_ID = c.Stadium_ID WHERE c.Year = '2014' INTERSECT SELECT s.Name, s.Location FROM stadium s JOIN concert c ON s.Stadium_ID = c.Stadium_ID WHERE c.Year = '2015';	concert_singer
SELECT s.Name, s.Location FROM stadium s JOIN concert c ON s.Stadium_ID = c.Stadium_ID WHERE c.Year = '2014' INTERSECT SELECT s.Name, s.Location FROM stadium s JOIN concert c ON s.Stadium_ID = c.Stadium_ID WHERE c.Year = '2015';	concert_singer
SELECT COUNT(*) FROM concert AS t1 JOIN stadium AS t2 ON t1.Stadium_ID = t2.Stadium_ID WHERE t2.Capacity = (SELECT MAX(Capacity) FROM stadium);	concert_singer
SELECT COUNT(*) FROM concert JOIN stadium ON concert.Stadium_ID = stadium.Stadium_ID WHERE stadium.Capacity = (SELECT MAX(Capacity) FROM stadium);	concert_singer
SELECT COUNT(*) FROM Pets WHERE weight > 10;	pets_1
SELECT COUNT(*) FROM Pets WHERE weight > 10;	pets_1
SELECT weight FROM Pets WHERE PetType = 'dog' ORDER BY pet_age ASC LIMIT 1;	pets_1
SELECT weight FROM Pets WHERE PetType = 'dog' ORDER BY pet_age ASC LIMIT 1;	pets_1
SELECT MAX(weight), PetType FROM Pets GROUP BY PetType;	pets_1
SELECT PetType, MAX(weight) FROM Pets GROUP BY PetType;	pets_1
SELECT COUNT(*) FROM Has_Pet hp JOIN Student s ON hp.StuID = s.StuID WHERE s.age > 20;	pets_1
SELECT COUNT(*) FROM Has_Pet hp JOIN Student s ON hp.StuID = s.StuID WHERE s.age > 20;	pets_1
SELECT COUNT(*) FROM Has_Pet hp JOIN Student s ON hp.StuID = s.StuID JOIN Pets p ON hp.PetID = p.PetID WHERE s.Sex = 'F' AND p.PetType = 'dog';	pets_1
SELECT COUNT(*) FROM Has_Pet AS HP JOIN Student AS S ON HP.StuID = S.StuID JOIN Pets AS P ON HP.PetID = P.PetID WHERE S.Sex = 'F' AND P.PetType = 'dog';	pets_1
SELECT count(DISTINCT PetType) FROM Pets;	pets_1
SELECT COUNT(DISTINCT PetType) FROM Pets;	pets_1
SELECT DISTINCT Student.Fname FROM Student JOIN Has_Pet ON Student.StuID = Has_Pet.StuID JOIN Pets ON Has_Pet.PetID = Pets.PetID WHERE Pets.PetType IN ('Cat', 'Dog');	pets_1
SELECT DISTINCT T2.Fname FROM Has_Pet AS T1 JOIN Student AS T2 ON T1.StuID = T2.StuID JOIN Pets AS T3 ON T1.PetID = T3.PetID WHERE T3.PetType IN ('cat', 'dog');	pets_1
SELECT S.Fname FROM Student S JOIN Has_Pet HP1 ON S.StuID = HP1.StuID JOIN Pets P1 ON HP1.PetID = P1.PetID JOIN Has_Pet HP2 ON S.StuID = HP2.StuID JOIN Pets P2 ON HP2.PetID = P2.PetID WHERE P1.PetType = 'Cat' AND P2.PetType = 'Dog';	pets_1
SELECT DISTINCT s.Fname FROM Student s JOIN Has_Pet hp ON s.StuID = hp.StuID JOIN Pets p ON hp.PetID = p.PetID WHERE p.PetType = 'cat' INTERSECT SELECT DISTINCT s.Fname FROM Student s JOIN Has_Pet hp ON s.StuID = hp.StuID JOIN Pets p ON hp.PetID = p.PetID WHERE p.PetType = 'dog';	pets_1
SELECT Major, Age FROM Student WHERE StuID NOT IN (SELECT StuID FROM Has_Pet WHERE PetID IN (SELECT PetID FROM Pets WHERE PetType = 'cat'))	pets_1
SELECT Major, Age FROM Student WHERE StuID NOT IN ( SELECT StuID FROM Has_Pet WHERE PetID IN ( SELECT PetID FROM Pets WHERE PetType = 'cat' ) );	pets_1
SELECT StuID FROM Student WHERE StuID NOT IN (SELECT StuID FROM Has_Pet WHERE PetID IN (SELECT PetID FROM Pets WHERE PetType = "cat"))	pets_1
SELECT StuID FROM Student WHERE StuID NOT IN (SELECT StuID FROM Has_Pet WHERE PetID IN (SELECT PetID FROM Pets WHERE PetType = 'cat'))	pets_1
SELECT S.Fname, S.Age FROM Student S WHERE S.StuID IN (SELECT HP.StuID FROM Has_Pet HP JOIN Pets P ON HP.PetID = P.PetID WHERE P.PetType = 'dog') AND S.StuID NOT IN (SELECT HP.StuID FROM Has_Pet HP JOIN Pets P ON HP.PetID = P.PetID WHERE P.PetType = 'cat')	pets_1
SELECT DISTINCT S.Fname FROM Student S WHERE S.StuID IN (SELECT HP.StuID FROM Has_Pet HP JOIN Pets P ON HP.PetID = P.PetID WHERE P.PetType = 'dog') AND S.StuID NOT IN (SELECT HP.StuID FROM Has_Pet HP JOIN Pets P ON HP.PetID = P.PetID WHERE P.PetType = 'cat');	pets_1
SELECT PetType, weight FROM Pets ORDER BY pet_age ASC LIMIT 1;	pets_1
SELECT PetType, weight FROM Pets ORDER BY pet_age ASC LIMIT 1;	pets_1
SELECT PetID, weight FROM Pets WHERE pet_age > 1;	pets_1
SELECT PetID, weight FROM Pets WHERE pet_age > 1;	pets_1
SELECT Pets.PetType, AVG(Pets.pet_age) AS AverageAge, MAX(Pets.pet_age) AS MaximumAge FROM Pets JOIN Has_Pet ON Pets.PetID = Has_Pet.PetID GROUP BY Pets.PetType;	pets_1
SELECT Pets.PetType, AVG(Pets.pet_age) AS AverageAge, MAX(Pets.pet_age) AS MaximumAge FROM Pets JOIN Has_Pet ON Pets.PetID = Has_Pet.PetID GROUP BY Pets.PetType;	pets_1
SELECT AVG(weight), PetType FROM Pets GROUP BY PetType;	pets_1
SELECT PetType, AVG(weight) FROM Pets GROUP BY PetType;	pets_1
SELECT Student.Fname, Student.Age FROM Student JOIN Has_Pet ON Student.StuID = Has_Pet.StuID;	pets_1
SELECT DISTINCT fname, age FROM Student WHERE StuID IN (SELECT StuID FROM Has_Pet);	pets_1
SELECT T1.PetID FROM Has_Pet AS T1 JOIN Student AS T2 ON T1.StuID = T2.StuID WHERE T2.LName = 'Smith';	pets_1
SELECT T1.PetID FROM Has_Pet AS T1 JOIN Student AS T2 ON T1.StuID = T2.StuID WHERE T2.LName = 'Smith';	pets_1
SELECT StuID, COUNT(PetID) AS NumberOfPets FROM Has_Pet GROUP BY StuID;	pets_1
SELECT StuID, COUNT(PetID) AS NumberOfPets FROM Has_Pet GROUP BY StuID;	pets_1
SELECT S.Fname, S.Sex FROM Student S JOIN Has_Pet HP ON S.StuID = HP.StuID GROUP BY S.StuID HAVING COUNT(HP.PetID) > 1;	pets_1
SELECT S.fname, S.sex FROM Student S JOIN Has_Pet HP ON S.StuID = HP.StuID GROUP BY S.StuID HAVING COUNT(HP.PetID) > 1;	pets_1
SELECT DISTINCT S.LName FROM Student S JOIN Has_Pet HP ON S.StuID = HP.StuID JOIN Pets P ON HP.PetID = P.PetID WHERE P.PetType = 'cat' AND P.pet_age = 3;	pets_1
SELECT Student.LName FROM Student JOIN Has_Pet ON Student.StuID = Has_Pet.StuID JOIN Pets ON Has_Pet.PetID = Pets.PetID WHERE Pets.PetType = 'cat' AND Pets.pet_age = 3;	pets_1
SELECT AVG(age) FROM Student WHERE StuID NOT IN (SELECT StuID FROM Has_Pet);	pets_1
SELECT AVG(age) FROM Student WHERE StuID NOT IN (SELECT StuID FROM Has_Pet);	pets_1
SELECT COUNT(*) FROM continents;	car_1
SELECT COUNT(*) FROM continents;	car_1
SELECT T1.ContId, T1.Continent, COUNT(T2.CountryId) FROM continents AS T1 JOIN countries AS T2 ON T1.ContId = T2.Continent GROUP BY T1.ContId, T1.Continent;	car_1
SELECT continents.ContId, continents.Continent, COUNT(countries.CountryId) AS NumberOfCountries FROM continents JOIN countries ON continents.ContId = countries.Continent GROUP BY continents.ContId, continents.Continent;	car_1
SELECT COUNT(*) FROM countries;	car_1
SELECT count(*) FROM countries;	car_1
SELECT cm.FullName, cm.Id, COUNT(ml.Model) AS NumberOfModels FROM car_makers cm JOIN model_list ml ON cm.Id = ml.Maker GROUP BY cm.FullName, cm.Id;	car_1
SELECT cm.FullName, cm.Id, COUNT(ml.Model) AS ModelCount FROM car_makers cm JOIN model_list ml ON cm.Id = ml.Maker GROUP BY cm.Id, cm.FullName;	car_1
SELECT model_list.Model FROM model_list JOIN cars_data ON model_list.ModelId = cars_data.Id ORDER BY CAST(REPLACE(cars_data.Horsepower, ',', '') AS REAL) ASC LIMIT 1;	car_1
SELECT T1.Model FROM model_list AS T1 JOIN cars_data AS T2 ON T1.ModelId = T2.Id ORDER BY CAST(REPLACE(T2.Horsepower, ',', '') AS REAL) ASC LIMIT 1;	car_1
SELECT T1.Model FROM car_names AS T1 JOIN cars_data AS T2 ON T1.MakeId = T2.Id WHERE T2.Weight < (SELECT AVG(Weight) FROM cars_data);	car_1
SELECT T1.Model FROM car_names AS T1 JOIN cars_data AS T2 ON T1.MakeId = T2.Id WHERE T2.Weight < (SELECT AVG(Weight) FROM cars_data);	car_1
SELECT DISTINCT T2.Maker FROM cars_data AS T1 JOIN car_names AS T3 ON T1.Id = T3.MakeId JOIN model_list AS T4 ON T3.Model = T4.Model JOIN car_makers AS T2 ON T4.Maker = T2.Id WHERE T1.Year = 1970;	car_1
SELECT DISTINCT T3.FullName FROM cars_data AS T1 JOIN car_names AS T2 ON T1.Id = T2.MakeId JOIN car_makers AS T3 ON T2.Make = T3.Maker WHERE T1.Year = 1970;	car_1
SELECT T2.Make, T1.Year FROM cars_data AS T1 JOIN car_names AS T2 ON T1.Id = T2.MakeId ORDER BY T1.Year ASC LIMIT 1;	car_1
SELECT T3.Maker, T1.Year FROM cars_data AS T1 JOIN car_names AS T2 ON T1.Id = T2.MakeId JOIN model_list AS T3 ON T2.Model = T3.Model ORDER BY T1.Year ASC LIMIT 1;	car_1
SELECT DISTINCT T2.Model FROM cars_data AS T1 JOIN car_names AS T2 ON T1.Id = T2.MakeId WHERE T1.Year > 1980;	car_1
SELECT DISTINCT Model FROM cars_data JOIN car_names ON cars_data.Id = car_names.MakeId WHERE cars_data.Year > 1980;	car_1
SELECT c.Continent, COUNT(cm.Id) AS MakerCount FROM car_makers cm JOIN countries co ON cm.Country = co.CountryId JOIN continents c ON co.Continent = c.ContId GROUP BY c.Continent;	car_1
SELECT c.Continent, COUNT(cm.Id) AS NumberOfCarMakers FROM countries co JOIN continents c ON co.Continent = c.ContId JOIN car_makers cm ON co.CountryId = cm.Country GROUP BY c.Continent;	car_1
SELECT T2.CountryName FROM car_makers AS T1 JOIN countries AS T2 ON T1.Country = T2.CountryId GROUP BY T2.CountryName ORDER BY COUNT(T1.Id) DESC LIMIT 1;	car_1
SELECT T2.CountryName FROM car_makers AS T1 JOIN countries AS T2 ON T1.Country = T2.CountryId GROUP BY T2.CountryName ORDER BY COUNT(T1.Id) DESC LIMIT 1;	car_1
SELECT COUNT(T2.Model), T1.FullName FROM car_makers AS T1 JOIN model_list AS T2 ON T1.Id = T2.Maker GROUP BY T1.FullName;	car_1
SELECT cm.FullName, cm.Id, COUNT(ml.Model) AS NumberOfModels FROM car_makers cm JOIN model_list ml ON cm.Id = ml.Maker GROUP BY cm.FullName, cm.Id;	car_1
SELECT T1.Accelerate FROM cars_data AS T1 JOIN car_names AS T2 ON T1.Id = T2.MakeId WHERE T2.Make = 'amc hornet sportabout (sw)';	car_1
SELECT T1.Accelerate FROM cars_data AS T1 JOIN car_names AS T2 ON T1.Id = T2.MakeId WHERE T2.Make = 'amc hornet sportabout (sw)';	car_1
SELECT COUNT(*) FROM car_makers WHERE Country = (SELECT CountryId FROM countries WHERE CountryName = 'France');	car_1
SELECT COUNT(DISTINCT Maker) FROM car_makers JOIN countries ON car_makers.Country = countries.CountryId WHERE countries.CountryName = "France";	car_1
SELECT COUNT(DISTINCT ml.Model) FROM model_list ml JOIN car_makers cm ON ml.Maker = cm.Id JOIN countries c ON cm.Country = c.CountryId WHERE c.CountryName = 'USA';	car_1
SELECT COUNT(DISTINCT ml.Model) FROM car_makers cm JOIN model_list ml ON cm.Id = ml.Maker JOIN countries c ON cm.Country = c.CountryId WHERE c.CountryName = 'USA';	car_1
SELECT AVG(MPG) FROM cars_data WHERE Cylinders = 4;	car_1
SELECT AVG(MPG) FROM cars_data WHERE Cylinders = 4;	car_1
SELECT MIN(Weight) FROM cars_data WHERE Cylinders = 8 AND Year = 1974;	car_1
SELECT MIN(Weight) FROM cars_data WHERE Cylinders = 8 AND Year = 1974;	car_1
SELECT Maker, Model FROM model_list;	car_1
SELECT Maker, Model FROM model_list;	car_1
SELECT DISTINCT c.CountryName, cm.Country FROM car_makers cm JOIN countries c ON cm.Country = c.CountryId;	car_1
SELECT DISTINCT T2.CountryName, T1.Country FROM car_makers AS T1 JOIN countries AS T2 ON T1.Country = T2.CountryId;	car_1
SELECT COUNT(*) FROM cars_data WHERE Horsepower > 150;	car_1
SELECT COUNT(*) FROM cars_data WHERE Horsepower > 150;	car_1
SELECT Year, AVG(Weight) FROM cars_data GROUP BY Year;	car_1
SELECT AVG(Weight), Year FROM cars_data GROUP BY Year;	car_1
SELECT T1.CountryName FROM countries AS T1 JOIN continents AS T2 ON T1.Continent = T2.ContId JOIN car_makers AS T3 ON T1.CountryId = T3.Country WHERE T2.Continent = 'Europe' GROUP BY T1.CountryName HAVING COUNT(T3.Id) >= 3;	car_1
SELECT T1.CountryName FROM countries AS T1 JOIN continents AS T2 ON T1.Continent = T2.ContId JOIN car_makers AS T3 ON T1.CountryId = T3.Country WHERE T2.Continent = 'Europe' GROUP BY T1.CountryName HAVING COUNT(T3.Id) >= 3;	car_1
SELECT MAX(c.Horsepower), cn.Make FROM cars_data c JOIN car_names cn ON c.Id = cn.MakeId WHERE c.Cylinders = 3;	car_1
SELECT MAX(c.Horsepower), cn.Make FROM cars_data c JOIN car_names cn ON c.Id = cn.MakeId WHERE c.Cylinders = 3;	car_1
SELECT Model FROM car_names WHERE MakeId = (SELECT Id FROM cars_data ORDER BY MPG DESC LIMIT 1)	car_1
SELECT T1.Model FROM model_list AS T1 JOIN cars_data AS T2 ON T1.ModelId = T2.Id ORDER BY T2.MPG DESC LIMIT 1;	car_1
SELECT AVG(CAST(REPLACE(Horsepower, ',', '') AS REAL)) AS AverageHorsepower FROM cars_data WHERE Year < 1980;	car_1
SELECT AVG(CAST(REPLACE(Horsepower, ',', '') AS REAL)) AS AverageHorsepower FROM cars_data WHERE Year < 1980;	car_1
SELECT AVG(T1.Edispl) FROM cars_data AS T1 JOIN car_names AS T2 ON T1.Id = T2.MakeId JOIN model_list AS T3 ON T2.Model = T3.Model JOIN car_makers AS T4 ON T3.Maker = T4.Id WHERE T4.FullName = 'Volvo';	car_1
SELECT AVG(T1.Edispl) FROM cars_data AS T1 JOIN car_names AS T2 ON T1.Id = T2.MakeId WHERE T2.Make = 'volvo';	car_1
SELECT Cylinders, MAX(Accelerate) FROM cars_data GROUP BY Cylinders;	car_1
SELECT Cylinders, MAX(Accelerate) AS MaxAccelerate FROM cars_data GROUP BY Cylinders;	car_1
SELECT Model FROM car_names GROUP BY Model ORDER BY COUNT(Make) DESC LIMIT 1;	car_1
SELECT Model FROM car_names GROUP BY Model ORDER BY COUNT(*) DESC LIMIT 1;	car_1
SELECT COUNT(*) FROM cars_data WHERE Cylinders > 4;	car_1
SELECT COUNT(*) FROM cars_data WHERE Cylinders > 4;	car_1
SELECT COUNT(*) FROM cars_data WHERE Year = 1980;	car_1
SELECT COUNT(*) FROM cars_data WHERE Year = 1980;	car_1
SELECT COUNT(*) FROM model_list ml JOIN car_makers cm ON ml.Maker = cm.Id WHERE cm.FullName = 'American Motor Company';	car_1
SELECT COUNT(*) FROM model_list ml JOIN car_makers cm ON ml.Maker = cm.Id WHERE cm.FullName = 'American Motor Company';	car_1
SELECT T2.FullName, T1.Maker FROM model_list AS T1 JOIN car_makers AS T2 ON T1.Maker = T2.Id GROUP BY T1.Maker HAVING COUNT(T1.Model) > 3;	car_1
SELECT T2.Maker, T2.Id FROM model_list AS T1 JOIN car_makers AS T2 ON T1.Maker = T2.Id GROUP BY T2.Maker, T2.Id HAVING COUNT(T1.Model) > 3;	car_1
SELECT DISTINCT ml.Model FROM model_list ml JOIN car_makers cm ON ml.Maker = cm.Id JOIN car_names cn ON ml.Model = cn.Model JOIN cars_data cd ON cn.MakeId = cd.Id WHERE cm.FullName = 'General Motors' OR cd.Weight > 3500;	car_1
SELECT DISTINCT ml.Model FROM model_list ml JOIN car_makers cm ON ml.Maker = cm.Id JOIN car_names cn ON ml.Model = cn.Model JOIN cars_data cd ON cn.MakeId = cd.Id WHERE cm.FullName = 'General Motors' OR cd.Weight > 3500;	car_1
SELECT Year FROM cars_data WHERE Weight BETWEEN 3000 AND 4000;	car_1
SELECT DISTINCT Year FROM cars_data WHERE Weight < 4000 OR Weight > 3000;	car_1
SELECT Horsepower FROM cars_data ORDER BY Accelerate DESC LIMIT 1;	car_1
SELECT Horsepower FROM cars_data ORDER BY Accelerate DESC LIMIT 1;	car_1
SELECT C.Cylinders FROM cars_data C JOIN car_names CN ON C.Id = CN.MakeId JOIN model_list ML ON CN.Model = ML.Model WHERE ML.Maker = (SELECT Id FROM car_makers WHERE Maker = 'volvo') ORDER BY C.Accelerate ASC LIMIT 1;	car_1
SELECT C.Cylinders FROM cars_data C JOIN car_names CN ON C.Id = CN.MakeId JOIN model_list ML ON CN.Model = ML.Model JOIN car_makers CM ON ML.Maker = CM.Id WHERE CM.Maker = 'volvo' ORDER BY C.Accelerate ASC LIMIT 1;	car_1
SELECT COUNT(*) FROM cars_data WHERE Accelerate > (SELECT MAX(Horsepower) FROM cars_data);	car_1
SELECT COUNT(*) FROM cars_data WHERE Accelerate > (SELECT MAX(CAST(REPLACE(Horsepower, ',', '') AS REAL)) FROM cars_data);	car_1
SELECT Country, COUNT(*) as MakerCount FROM car_makers GROUP BY Country HAVING MakerCount > 2;	car_1
SELECT COUNT(*) FROM ( SELECT Country FROM car_makers GROUP BY Country HAVING COUNT(*) > 2 ) AS SubQuery;	car_1
SELECT COUNT(*) FROM cars_data WHERE Cylinders > 6;	car_1
SELECT COUNT(*) FROM cars_data WHERE Cylinders > 6;	car_1
SELECT T1.Model FROM car_names AS T1 JOIN cars_data AS T2 ON T1.MakeId = T2.Id WHERE T2.Cylinders = 4 ORDER BY CAST(REPLACE(T2.Horsepower, ',', '') AS REAL) DESC LIMIT 1;	car_1
SELECT T3.Model FROM cars_data AS T1 JOIN car_names AS T2 ON T1.Id = T2.MakeId JOIN model_list AS T3 ON T2.Model = T3.Model WHERE T1.Cylinders = 4 ORDER BY CAST(REPLACE(T1.Horsepower, ',', '') AS REAL) DESC LIMIT 1;	car_1
SELECT T1.MakeId, T1.Make FROM car_names AS T1 JOIN cars_data AS T2 ON T1.MakeId = T2.Id WHERE T2.Cylinders <= 3 AND T2.Horsepower > ( SELECT MIN(Horsepower) FROM cars_data );	car_1
SELECT T1.MakeId, T1.Make FROM car_names AS T1 JOIN cars_data AS T2 ON T1.MakeId = T2.Id WHERE T2.Cylinders < 4 AND T2.Horsepower != (SELECT MIN(Horsepower) FROM cars_data);	car_1
SELECT MAX(MPG) FROM cars_data WHERE Cylinders = 8 OR Year < 1980;	car_1
SELECT MAX(MPG) FROM cars_data WHERE Cylinders = 8 OR Year < 1980;	car_1
SELECT T1.Model FROM car_names AS T1 JOIN cars_data AS T2 ON T1.MakeId = T2.Id JOIN car_makers AS T3 ON T3.Country = T1.Make WHERE T2.Weight < 3500 AND T3.FullName != 'Ford Motor Company'	car_1
SELECT DISTINCT model_list.Model FROM cars_data JOIN model_list ON cars_data.Id = model_list.ModelId WHERE cars_data.Weight < 3500 AND model_list.Maker NOT IN ( SELECT Id FROM car_makers WHERE FullName = 'Ford Motor Company' );	car_1
SELECT CountryName FROM countries WHERE CountryId NOT IN (SELECT Country FROM car_makers);	car_1
SELECT CountryName FROM countries WHERE CountryId NOT IN (SELECT Country FROM car_makers);	car_1
SELECT Maker, COUNT(Model) AS ModelCount FROM model_list GROUP BY Maker HAVING COUNT(Model) >=2AND Maker IN ( SELECT Maker FROM model_list GROUP BY Maker HAVING COUNT(DISTINCT Model) > 3 )	car_1
SELECT cm.Id, cm.Maker FROM car_makers cm JOIN model_list ml ON cm.Id = ml.Maker JOIN cars_data cd ON ml.ModelId = cd.Id GROUP BY cm.Id, cm.Maker HAVING COUNT(DISTINCT ml.Model) >=2AND COUNT(cd.Id) > 3;	car_1
SELECT c.CountryId, c.CountryName FROM countries c JOIN car_makers cm ON c.CountryId = cm.Country GROUP BY c.CountryId, c.CountryName HAVING COUNT(cm.Id) > 3 UNION SELECT c.CountryId, c.CountryName FROM countries c JOIN car_makers cm ON c.CountryId = cm.Country JOIN model_list ml ON cm.Id = ml.Maker WHERE ml.Model = 'fiat'	car_1
SELECT DISTINCT c.CountryId, c.CountryName FROM countries c JOIN car_makers cm ON c.CountryId = cm.Country GROUP BY c.CountryId, c.CountryName HAVING COUNT(cm.Id) > 3 UNION SELECT DISTINCT c.CountryId, c.CountryName FROM countries c JOIN car_makers cm ON c.CountryId = cm.Country JOIN model_list ml ON cm.Id = ml.Maker JOIN car_names cn ON ml.Model = cn.Model WHERE cm.FullName = 'Fiat'	car_1
SELECT Country FROM airlines WHERE Airline = "JetBlue Airways";	flight_2
SELECT Country FROM airlines WHERE Airline = 'Jetblue Airways';	flight_2
SELECT Abbreviation FROM airlines WHERE Airline = "JetBlue Airways";	flight_2
SELECT Abbreviation FROM airlines WHERE Airline = 'Jetblue Airways';	flight_2
SELECT Airline, Abbreviation FROM airlines WHERE Country = 'USA';	flight_2
SELECT Airline, Abbreviation FROM airlines WHERE Country = 'USA';	flight_2
SELECT AirportCode, AirportName FROM airports WHERE City = 'Anthony';	flight_2
SELECT AirportCode, AirportName FROM airports WHERE City = 'Anthony';	flight_2
SELECT count(*) FROM airlines;	flight_2
SELECT count(*) FROM airlines;	flight_2
SELECT COUNT(*) FROM airports;	flight_2
SELECT COUNT(*) FROM airports;	flight_2
SELECT count(*) FROM flights;	flight_2
SELECT count(*) FROM flights;	flight_2
SELECT Airline FROM airlines WHERE Abbreviation = 'UAL';	flight_2
SELECT Airline FROM airlines WHERE Abbreviation = 'UAL';	flight_2
SELECT COUNT(*) FROM airlines WHERE Country = 'USA';	flight_2
SELECT count(*) FROM airlines WHERE Country = 'USA';	flight_2
SELECT City, Country FROM airports WHERE AirportName = 'Alton';	flight_2
SELECT City, Country FROM airports WHERE AirportName = 'Alton';	flight_2
SELECT AirportName FROM airports WHERE AirportCode = 'AKO';	flight_2
SELECT AirportName FROM airports WHERE AirportCode = 'AKO';	flight_2
SELECT AirportName FROM airports WHERE City = 'Aberdeen';	flight_2
SELECT AirportName FROM airports WHERE City = 'Aberdeen';	flight_2
SELECT COUNT(*) FROM flights WHERE SourceAirport = 'APG';	flight_2
SELECT COUNT(*) FROM flights WHERE SourceAirport = 'APG';	flight_2
SELECT COUNT(*) FROM flights WHERE DestAirport = 'ATO';	flight_2
SELECT COUNT(*) FROM flights WHERE DestAirport = 'ATO';	flight_2
SELECT COUNT(*) FROM flights JOIN airports ON flights.SourceAirport = airports.AirportCode WHERE airports.City = 'Aberdeen';	flight_2
SELECT COUNT(*) FROM flights JOIN airports ON flights.SourceAirport = airports.AirportCode WHERE airports.City = 'Aberdeen';	flight_2
SELECT COUNT(*) FROM flights JOIN airports ON flights.DestAirport = airports.AirportCode WHERE airports.City = 'Aberdeen';	flight_2
SELECT COUNT(*) FROM flights JOIN airports ON flights.DestAirport = airports.AirportCode WHERE airports.City = 'Aberdeen';	flight_2
SELECT COUNT(*) FROM flights f JOIN airports src ON f.SourceAirport = src.AirportCode JOIN airports dest ON f.DestAirport = dest.AirportCode WHERE src.City = 'Aberdeen' AND dest.City = 'Ashley';	flight_2
SELECT COUNT(*) FROM flights WHERE SourceAirport = (SELECT AirportCode FROM airports WHERE City = 'Aberdeen') AND DestAirport = (SELECT AirportCode FROM airports WHERE City = 'Ashley');	flight_2
SELECT COUNT(*) FROM flights AS T1 JOIN airlines AS T2 ON T1.Airline = T2.uid WHERE T2.Airline = 'JetBlue Airways';	flight_2
SELECT COUNT(*) FROM flights JOIN airlines ON flights.Airline = airlines.uid WHERE airlines.Airline = 'JetBlue Airways';	flight_2
SELECT COUNT(*) FROM flights JOIN airlines ON flights.Airline = airlines.uid WHERE airlines.Airline = 'United Airlines' AND flights.DestAirport = 'ASY';	flight_2
SELECT COUNT(*) FROM flights AS F JOIN airlines AS A ON F.Airline = A.uid JOIN airports AS AP ON F.DestAirport = AP.AirportCode WHERE A.Airline = 'United Airlines' AND AP.AirportCode = 'ASY';	flight_2
SELECT COUNT(*) FROM flights JOIN airlines ON flights.Airline = airlines.uid WHERE airlines.Airline = 'United Airlines' AND flights.SourceAirport = 'AHD';	flight_2
SELECT COUNT(*) FROM flights AS F JOIN airlines AS A ON F.Airline = A.uid WHERE A.Airline = 'United Airlines' AND F.SourceAirport = 'AHD';	flight_2
SELECT COUNT(*) FROM flights f JOIN airlines a ON f.Airline = a.uid JOIN airports ap ON f.DestAirport = ap.AirportCode WHERE a.Airline = 'United Airlines' AND ap.City = 'Aberdeen';	flight_2
SELECT COUNT(*) FROM flights f JOIN airlines a ON f.Airline = a.uid JOIN airports ap ON f.DestAirport = ap.AirportCode WHERE a.Airline = 'United Airlines' AND ap.City = 'Aberdeen';	flight_2
SELECT t2.City FROM flights AS t1 JOIN airports AS t2 ON t1.DestAirport = t2.AirportCode GROUP BY t2.City ORDER BY COUNT(*) DESC LIMIT 1;	flight_2
SELECT T1.City FROM airports AS T1 JOIN flights AS T2 ON T1.AirportCode = T2.DestAirport GROUP BY T1.City ORDER BY COUNT(*) DESC LIMIT 1;	flight_2
SELECT t2.City FROM flights AS t1 JOIN airports AS t2 ON t1.SourceAirport = t2.AirportCode GROUP BY t2.City ORDER BY COUNT(*) DESC LIMIT 1;	flight_2
SELECT T1.City FROM airports AS T1 JOIN flights AS T2 ON T1.AirportCode = T2.SourceAirport GROUP BY T1.City ORDER BY COUNT(*) DESC LIMIT 1;	flight_2
SELECT SourceAirport AS AirportCode FROM flights GROUP BY SourceAirport ORDER BY COUNT(*) DESC LIMIT 1;	flight_2
SELECT SourceAirport AS AirportCode FROM flights GROUP BY SourceAirport ORDER BY COUNT(*) DESC LIMIT 1;	flight_2
SELECT SourceAirport AS AirportCode FROM flights GROUP BY SourceAirport ORDER BY COUNT(*) ASC LIMIT 1;	flight_2
SELECT SourceAirport FROM flights GROUP BY SourceAirport ORDER BY COUNT(*) ASC LIMIT 1;	flight_2
SELECT T1.Airline FROM airlines AS T1 JOIN flights AS T2 ON T1.uid = T2.Airline GROUP BY T1.Airline ORDER BY COUNT(*) DESC LIMIT 1;	flight_2
SELECT T1.Airline FROM airlines AS T1 JOIN flights AS T2 ON T1.uid = T2.Airline GROUP BY T1.Airline ORDER BY COUNT(*) DESC LIMIT 1;	flight_2
SELECT T1.Abbreviation, T1.Country FROM airlines AS T1 JOIN flights AS T2 ON T1.uid = T2.Airline GROUP BY T1.uid ORDER BY COUNT(*) ASC LIMIT 1;	flight_2
SELECT T1.Abbreviation, T1.Country FROM airlines AS T1 JOIN flights AS T2 ON T1.uid = T2.Airline GROUP BY T1.Abbreviation, T1.Country ORDER BY COUNT(*) ASC LIMIT 1;	flight_2
SELECT DISTINCT T1.Airline FROM airlines AS T1 JOIN flights AS T2 ON T1.uid = T2.Airline WHERE T2.SourceAirport = 'AHD';	flight_2
SELECT DISTINCT T1.Airline FROM airlines AS T1 JOIN flights AS T2 ON T1.uid = T2.Airline WHERE T2.SourceAirport = 'AHD';	flight_2
SELECT DISTINCT T1.Airline FROM airlines AS T1 JOIN flights AS T2 ON T1.uid = T2.Airline WHERE T2.DestAirport = 'AHD';	flight_2
SELECT DISTINCT T1.Airline FROM airlines AS T1 JOIN flights AS T2 ON T1.uid = T2.Airline WHERE T2.DestAirport = 'AHD';	flight_2
SELECT T1.Airline FROM airlines AS T1 JOIN flights AS T2 ON T1.uid = T2.Airline WHERE T2.SourceAirport = 'APG' INTERSECT SELECT T1.Airline FROM airlines AS T1 JOIN flights AS T2 ON T1.uid = T2.Airline WHERE T2.SourceAirport = 'CVO';	flight_2
SELECT T1.Airline FROM airlines AS T1 JOIN flights AS T2 ON T1.uid = T2.Airline WHERE T2.SourceAirport = 'APG' INTERSECT SELECT T1.Airline FROM airlines AS T1 JOIN flights AS T2 ON T1.uid = T2.Airline WHERE T2.SourceAirport = 'CVO';	flight_2
SELECT DISTINCT T1.Airline FROM airlines AS T1 JOIN flights AS T2 ON T1.uid = T2.Airline WHERE T2.SourceAirport = 'CVO' AND T1.uid NOT IN ( SELECT T1.uid FROM airlines AS T1 JOIN flights AS T2 ON T1.uid = T2.Airline WHERE T2.SourceAirport = 'APG' );	flight_2
SELECT DISTINCT T1.Airline FROM airlines AS T1 JOIN flights AS T2 ON T1.uid = T2.Airline WHERE T2.SourceAirport = 'CVO' AND T1.uid NOT IN ( SELECT T1.uid FROM airlines AS T1 JOIN flights AS T2 ON T1.uid = T2.Airline WHERE T2.SourceAirport = 'APG' );	flight_2
SELECT T1.Airline FROM airlines AS T1 JOIN flights AS T2 ON T1.uid = T2.Airline GROUP BY T1.Airline HAVING COUNT(T2.FlightNo) >= 10;	flight_2
SELECT T1.Airline FROM airlines AS T1 JOIN flights AS T2 ON T1.uid = T2.Airline GROUP BY T1.Airline HAVING COUNT(T2.FlightNo) >= 10;	flight_2
SELECT T1.Airline FROM airlines AS T1 JOIN flights AS T2 ON T1.uid = T2.Airline GROUP BY T1.Airline HAVING COUNT(T2.FlightNo) < 200;	flight_2
SELECT T1.Airline FROM airlines AS T1 JOIN flights AS T2 ON T1.uid = T2.Airline GROUP BY T1.Airline HAVING COUNT(T2.FlightNo) < 200;	flight_2
SELECT T1.FlightNo FROM flights AS T1 JOIN airlines AS T2 ON T1.Airline = T2.uid WHERE T2.Airline = "United Airlines";	flight_2
SELECT FlightNo FROM flights WHERE Airline = (SELECT uid FROM airlines WHERE Airline = 'United Airlines')	flight_2
SELECT FlightNo FROM flights WHERE SourceAirport = "APG";	flight_2
SELECT FlightNo FROM flights WHERE SourceAirport = "APG";	flight_2
SELECT FlightNo FROM flights WHERE DestAirport = "APG";	flight_2
SELECT FlightNo FROM flights WHERE DestAirport = 'APG';	flight_2
SELECT FlightNo FROM flights WHERE SourceAirport IN ( SELECT AirportCode FROM airports WHERE City = "Aberdeen" );	flight_2
SELECT FlightNo FROM flights WHERE SourceAirport = (SELECT AirportCode FROM airports WHERE City = "Aberdeen");	flight_2
SELECT FlightNo FROM flights WHERE DestAirport IN (SELECT AirportCode FROM airports WHERE City = "Aberdeen");	flight_2
SELECT FlightNo FROM flights WHERE DestAirport = (SELECT AirportCode FROM airports WHERE City = "Aberdeen");	flight_2
SELECT COUNT(*) FROM flights JOIN airports ON flights.DestAirport = airports.AirportCode WHERE airports.City IN ('Aberdeen', 'Abilene');	flight_2
SELECT COUNT(*) FROM flights WHERE DestAirport IN ( SELECT AirportCode FROM airports WHERE City IN ('Aberdeen', 'Abilene') );	flight_2
SELECT AirportName FROM airports WHERE AirportCode NOT IN (SELECT SourceAirport FROM flights UNION SELECT DestAirport FROM flights);	flight_2
SELECT AirportName FROM airports WHERE AirportCode NOT IN (SELECT SourceAirport FROM flights UNION SELECT DestAirport FROM flights);	flight_2
SELECT count(*) FROM employee;	employee_hire_evaluation
SELECT COUNT(*) FROM employee;	employee_hire_evaluation
SELECT Name FROM employee ORDER BY Age ASC;	employee_hire_evaluation
SELECT Name FROM employee ORDER BY Age ASC;	employee_hire_evaluation
SELECT City, COUNT(*) FROM employee GROUP BY City;	employee_hire_evaluation
SELECT City, COUNT(*) FROM employee GROUP BY City;	employee_hire_evaluation
SELECT City FROM employee WHERE Age < 30 GROUP BY City HAVING COUNT(*) > 1;	employee_hire_evaluation
SELECT City FROM employee WHERE Age < 30 GROUP BY City HAVING COUNT(Employee_ID) > 1;	employee_hire_evaluation
SELECT Location, COUNT(*) AS Number_of_Shops FROM shop GROUP BY Location;	employee_hire_evaluation
SELECT Location, COUNT(*) AS Number_of_Shops FROM shop GROUP BY Location;	employee_hire_evaluation
SELECT Manager_name, District FROM shop ORDER BY Number_products DESC LIMIT 1;	employee_hire_evaluation
SELECT Manager_name, District FROM shop ORDER BY Number_products DESC LIMIT 1;	employee_hire_evaluation
SELECT min(Number_products), max(Number_products) FROM shop;	employee_hire_evaluation
SELECT min(Number_products), max(Number_products) FROM shop;	employee_hire_evaluation
SELECT Name, Location, District FROM shop ORDER BY Number_products DESC;	employee_hire_evaluation
SELECT Name, Location, District FROM shop ORDER BY Number_products DESC;	employee_hire_evaluation
SELECT Name FROM shop WHERE Number_products > (SELECT AVG(Number_products) FROM shop)	employee_hire_evaluation
SELECT Name FROM shop WHERE Number_products > (SELECT AVG(Number_products) FROM shop)	employee_hire_evaluation
SELECT T1.Name FROM employee AS T1 JOIN evaluation AS T2 ON T1.Employee_ID = T2.Employee_ID GROUP BY T1.Employee_ID ORDER BY COUNT(T2.Year_awarded) DESC LIMIT 1;	employee_hire_evaluation
SELECT T2.Name FROM evaluation AS T1 JOIN employee AS T2 ON T1.Employee_ID = T2.Employee_ID GROUP BY T1.Employee_ID ORDER BY COUNT(*) DESC LIMIT 1;	employee_hire_evaluation
SELECT t1.Name FROM employee AS t1 JOIN evaluation AS t2 ON t1.Employee_ID = t2.Employee_ID ORDER BY t2.Bonus DESC LIMIT 1;	employee_hire_evaluation
SELECT T2.Name FROM evaluation AS T1 JOIN employee AS T2 ON T1.Employee_ID = T2.Employee_ID ORDER BY T1.Bonus DESC LIMIT 1;	employee_hire_evaluation
SELECT Name FROM employee WHERE Employee_ID NOT IN (SELECT Employee_ID FROM evaluation)	employee_hire_evaluation
SELECT Name FROM employee WHERE Employee_ID NOT IN (SELECT Employee_ID FROM evaluation)	employee_hire_evaluation
SELECT s.Name FROM shop s JOIN hiring h ON s.Shop_ID = h.Shop_ID GROUP BY s.Shop_ID ORDER BY COUNT(h.Employee_ID) DESC LIMIT 1;	employee_hire_evaluation
SELECT Name FROM shop WHERE Shop_ID = (SELECT Shop_ID FROM hiring GROUP BY Shop_ID ORDER BY COUNT(Employee_ID) DESC LIMIT 1)	employee_hire_evaluation
SELECT Name FROM shop WHERE Shop_ID NOT IN (SELECT Shop_ID FROM hiring);	employee_hire_evaluation
SELECT Name FROM shop WHERE Shop_ID NOT IN (SELECT Shop_ID FROM hiring);	employee_hire_evaluation
SELECT shop.Name, COUNT(hiring.Employee_ID) AS Number_of_Employees FROM shop JOIN hiring ON shop.Shop_ID = hiring.Shop_ID GROUP BY shop.Name;	employee_hire_evaluation
SELECT shop.Name, COUNT(hiring.Employee_ID) AS Number_of_Employees FROM shop JOIN hiring ON shop.Shop_ID = hiring.Shop_ID GROUP BY shop.Shop_ID, shop.Name;	employee_hire_evaluation
SELECT SUM(Bonus) FROM evaluation;	employee_hire_evaluation
SELECT SUM(Bonus) FROM evaluation;	employee_hire_evaluation
SELECT Shop_ID, Employee_ID, Start_from, Is_full_time FROM hiring;	employee_hire_evaluation
SELECT Shop_ID, Employee_ID, Start_from, Is_full_time FROM hiring;	employee_hire_evaluation
SELECT District FROM shop WHERE Number_products <3000 INTERSECT SELECT District FROM shop WHERE Number_products > 10000;	employee_hire_evaluation
SELECT District FROM shop WHERE Number_products <3000 INTERSECT SELECT District FROM shop WHERE Number_products > 10000;	employee_hire_evaluation
SELECT COUNT(DISTINCT Location) FROM shop;	employee_hire_evaluation
SELECT COUNT(DISTINCT Location) FROM shop;	employee_hire_evaluation
SELECT count(*) FROM Documents;	cre_Doc_Template_Mgt
SELECT count(*) FROM Documents;	cre_Doc_Template_Mgt
SELECT document_id, document_name, document_description FROM Documents;	cre_Doc_Template_Mgt
SELECT document_id, document_name, document_description FROM Documents;	cre_Doc_Template_Mgt
SELECT Document_Name, Template_ID FROM Documents WHERE Document_Description LIKE '%w%';	cre_Doc_Template_Mgt
SELECT Document_Name, Template_ID FROM Documents WHERE Document_Description LIKE '%w%';	cre_Doc_Template_Mgt
SELECT Document_ID, Template_ID, Document_Description FROM Documents WHERE Document_Name = 'Robbin CV';	cre_Doc_Template_Mgt
SELECT Document_ID, Template_ID, Document_Description FROM Documents WHERE Document_Name = 'Robbin CV';	cre_Doc_Template_Mgt
SELECT COUNT(DISTINCT Template_ID) FROM Documents;	cre_Doc_Template_Mgt
SELECT COUNT(DISTINCT Template_ID) FROM Documents;	cre_Doc_Template_Mgt
SELECT COUNT(*) FROM Documents JOIN Templates ON Documents.Template_ID = Templates.Template_ID WHERE Templates.Template_Type_Code = 'PPT';	cre_Doc_Template_Mgt
SELECT COUNT(*) FROM Documents JOIN Templates ON Documents.Template_ID = Templates.Template_ID JOIN Ref_Template_Types ON Templates.Template_Type_Code = Ref_Template_Types.Template_Type_Code WHERE Ref_Template_Types.Template_Type_Code = 'PPT';	cre_Doc_Template_Mgt
SELECT Template_ID, COUNT(Document_ID) FROM Documents GROUP BY Template_ID;	cre_Doc_Template_Mgt
SELECT Template_ID, COUNT(*) FROM Documents GROUP BY Template_ID;	cre_Doc_Template_Mgt
SELECT T.Template_ID, T.Template_Type_Code FROM Templates T JOIN Documents D ON T.Template_ID = D.Template_ID GROUP BY T.Template_ID, T.Template_Type_Code ORDER BY COUNT(D.Document_ID) DESC LIMIT 1;	cre_Doc_Template_Mgt
SELECT T.Template_ID, T.Template_Type_Code FROM Templates T JOIN Documents D ON T.Template_ID = D.Template_ID GROUP BY T.Template_ID, T.Template_Type_Code ORDER BY COUNT(D.Document_ID) DESC LIMIT 1;	cre_Doc_Template_Mgt
SELECT Template_ID FROM Documents GROUP BY Template_ID HAVING COUNT(Document_ID) > 1;	cre_Doc_Template_Mgt
SELECT Template_ID FROM Documents GROUP BY Template_ID HAVING COUNT(*) > 1;	cre_Doc_Template_Mgt
SELECT Template_ID FROM Templates WHERE Template_ID NOT IN (SELECT Template_ID FROM Documents);	cre_Doc_Template_Mgt
SELECT Template_ID FROM Templates WHERE Template_ID NOT IN (SELECT Template_ID FROM Documents);	cre_Doc_Template_Mgt
SELECT COUNT(*) FROM Templates;	cre_Doc_Template_Mgt
SELECT COUNT(*) FROM Templates;	cre_Doc_Template_Mgt
SELECT Template_ID, Version_Number, Template_Type_Code FROM Templates;	cre_Doc_Template_Mgt
SELECT Template_ID, Version_Number, Template_Type_Code FROM Templates;	cre_Doc_Template_Mgt
SELECT DISTINCT Template_Type_Code FROM Templates;	cre_Doc_Template_Mgt
SELECT Template_Type_Code FROM Ref_Template_Types;	cre_Doc_Template_Mgt
SELECT Template_ID FROM Templates WHERE Template_Type_Code IN ('PP', 'PPT');	cre_Doc_Template_Mgt
SELECT Template_ID FROM Templates WHERE Template_Type_Code IN ('PP', 'PPT');	cre_Doc_Template_Mgt
SELECT COUNT(*) FROM Templates WHERE Template_Type_Code = "CV";	cre_Doc_Template_Mgt
SELECT COUNT(*) FROM Templates WHERE Template_Type_Code = 'CV';	cre_Doc_Template_Mgt
SELECT Version_Number, Template_Type_Code FROM Templates WHERE Version_Number > 5;	cre_Doc_Template_Mgt
SELECT Version_Number, Template_Type_Code FROM Templates WHERE Version_Number > 5;	cre_Doc_Template_Mgt
SELECT Template_Type_Code, COUNT(*) FROM Templates GROUP BY Template_Type_Code;	cre_Doc_Template_Mgt
SELECT Template_Type_Code, COUNT(*) FROM Templates GROUP BY Template_Type_Code;	cre_Doc_Template_Mgt
SELECT Template_Type_Code FROM Templates GROUP BY Template_Type_Code ORDER BY COUNT(*) DESC LIMIT 1;	cre_Doc_Template_Mgt
SELECT Template_Type_Code FROM Templates GROUP BY Template_Type_Code ORDER BY COUNT(*) DESC LIMIT 1;	cre_Doc_Template_Mgt
SELECT Template_Type_Code FROM Templates GROUP BY Template_Type_Code HAVING COUNT(Template_ID) < 3;	cre_Doc_Template_Mgt
SELECT Template_Type_Code FROM Templates GROUP BY Template_Type_Code HAVING COUNT(*) < 3;	cre_Doc_Template_Mgt
SELECT Version_Number, Template_Type_Code FROM Templates ORDER BY Version_Number ASC LIMIT 1;	cre_Doc_Template_Mgt
SELECT Version_Number, Template_Type_Code FROM Templates ORDER BY Version_Number ASC LIMIT 1;	cre_Doc_Template_Mgt
SELECT T2.Template_Type_Code FROM Documents AS T1 JOIN Templates AS T2 ON T1.Template_ID = T2.Template_ID WHERE T1.Document_Name = 'Data base';	cre_Doc_Template_Mgt
SELECT T2.Template_Type_Code FROM Documents AS T1 JOIN Templates AS T2 ON T1.Template_ID = T2.Template_ID WHERE T1.Document_Name = "Data base";	cre_Doc_Template_Mgt
SELECT Document_Name FROM Documents JOIN Templates ON Documents.Template_ID = Templates.Template_ID WHERE Templates.Template_Type_Code = "BK";	cre_Doc_Template_Mgt
SELECT document_name FROM Documents JOIN Templates ON Documents.Template_ID = Templates.Template_ID WHERE Templates.Template_Type_Code = "BK";	cre_Doc_Template_Mgt
SELECT T1.Template_Type_Code, COUNT(DISTINCT T3.Document_ID) FROM Ref_Template_Types AS T1 JOIN Templates AS T2 ON T1.Template_Type_Code = T2.Template_Type_Code JOIN Documents AS T3 ON T2.Template_ID = T3.Template_ID GROUP BY T1.Template_Type_Code;	cre_Doc_Template_Mgt
SELECT T1.Template_Type_Code, COUNT(DISTINCT T3.Document_ID) FROM Ref_Template_Types AS T1 JOIN Templates AS T2 ON T1.Template_Type_Code = T2.Template_Type_Code JOIN Documents AS T3 ON T2.Template_ID = T3.Template_ID GROUP BY T1.Template_Type_Code;	cre_Doc_Template_Mgt
SELECT Template_Type_Code FROM Documents JOIN Templates ON Documents.Template_ID = Templates.Template_ID GROUP BY Template_Type_Code ORDER BY COUNT(*) DESC LIMIT 1;	cre_Doc_Template_Mgt
SELECT Template_Type_Code FROM Documents JOIN Templates ON Documents.Template_ID = Templates.Template_ID GROUP BY Template_Type_Code ORDER BY COUNT(*) DESC LIMIT 1;	cre_Doc_Template_Mgt
SELECT Template_Type_Code FROM Templates WHERE Template_ID NOT IN (SELECT Template_ID FROM Documents);	cre_Doc_Template_Mgt
SELECT Template_Type_Code FROM Ref_Template_Types WHERE Template_Type_Code NOT IN (SELECT Template_Type_Code FROM Templates WHERE Template_ID IN (SELECT Template_ID FROM Documents))	cre_Doc_Template_Mgt
SELECT Template_Type_Code, Template_Type_Description FROM Ref_Template_Types;	cre_Doc_Template_Mgt
SELECT Template_Type_Code, Template_Type_Description FROM Ref_Template_Types;	cre_Doc_Template_Mgt
SELECT Template_Type_Description FROM Ref_Template_Types WHERE Template_Type_Code = 'AD';	cre_Doc_Template_Mgt
SELECT Template_Type_Description FROM Ref_Template_Types WHERE Template_Type_Code = "AD";	cre_Doc_Template_Mgt
SELECT Template_Type_Code FROM Ref_Template_Types WHERE Template_Type_Description = "Book";	cre_Doc_Template_Mgt
SELECT Template_Type_Code FROM Ref_Template_Types WHERE Template_Type_Description = 'Book';	cre_Doc_Template_Mgt
SELECT DISTINCT T3.Template_Type_Description FROM Documents AS T1 JOIN Templates AS T2 ON T1.Template_ID = T2.Template_ID JOIN Ref_Template_Types AS T3 ON T2.Template_Type_Code = T3.Template_Type_Code;	cre_Doc_Template_Mgt
SELECT DISTINCT Template_Details FROM Templates WHERE Template_ID IN (SELECT Template_ID FROM Documents);	cre_Doc_Template_Mgt
SELECT T2.Template_ID FROM Ref_Template_Types AS T1 JOIN Templates AS T2 ON T1.Template_Type_Code = T2.Template_Type_Code WHERE T1.Template_Type_Description = 'Presentation';	cre_Doc_Template_Mgt
SELECT Template_ID FROM Templates WHERE Template_Details = 'Presentation';	cre_Doc_Template_Mgt
SELECT COUNT(*) FROM Paragraphs;	cre_Doc_Template_Mgt
SELECT COUNT(*) FROM Paragraphs;	cre_Doc_Template_Mgt
SELECT COUNT(*) FROM Paragraphs AS t1 JOIN Documents AS t2 ON t1.Document_ID = t2.Document_ID WHERE t2.Document_Name = 'Summer Show';	cre_Doc_Template_Mgt
SELECT COUNT(*) FROM Paragraphs AS P JOIN Documents AS D ON P.Document_ID = D.Document_ID WHERE D.Document_Name = 'Summer Show';	cre_Doc_Template_Mgt
SELECT Paragraph_Text, Other_Details FROM Paragraphs WHERE Paragraph_Text = 'Korea ';	cre_Doc_Template_Mgt
SELECT Paragraph_Text FROM Paragraphs WHERE Paragraph_Text LIKE '%Korea%';	cre_Doc_Template_Mgt
SELECT Paragraph_ID, Paragraph_Text FROM Paragraphs JOIN Documents ON Paragraphs.Document_ID = Documents.Document_ID WHERE Documents.Document_Name = 'Welcome to NY';	cre_Doc_Template_Mgt
SELECT Paragraph_ID, Paragraph_Text FROM Paragraphs JOIN Documents ON Paragraphs.Document_ID = Documents.Document_ID WHERE Documents.Document_Name = 'Welcome to NY';	cre_Doc_Template_Mgt
SELECT Paragraph_Text FROM Paragraphs JOIN Documents ON Paragraphs.Document_ID = Documents.Document_ID WHERE Documents.Document_Name = 'Customer reviews';	cre_Doc_Template_Mgt
SELECT Paragraph_Text FROM Paragraphs JOIN Documents ON Paragraphs.Document_ID = Documents.Document_ID WHERE Documents.Document_Name = 'Customer reviews';	cre_Doc_Template_Mgt
SELECT Documents.Document_ID, COUNT(Paragraphs.Paragraph_ID) AS NumberOfParagraphs FROM Documents JOIN Paragraphs ON Documents.Document_ID = Paragraphs.Document_ID GROUP BY Documents.Document_ID ORDER BY Documents.Document_ID;	cre_Doc_Template_Mgt
SELECT document_id, COUNT(paragraph_id) AS paragraph_count FROM Paragraphs GROUP BY document_id ORDER BY document_id;	cre_Doc_Template_Mgt
SELECT D.document_id, D.document_name, COUNT(P.Paragraph_ID) AS paragraph_count FROM Documents D LEFT JOIN Paragraphs P ON D.document_id = P.document_id GROUP BY D.document_id, D.document_name;	cre_Doc_Template_Mgt
SELECT d.Document_ID, d.Document_Name, COUNT(p.Paragraph_ID) AS Number_of_Paragraphs FROM Documents d JOIN Paragraphs p ON d.Document_ID = p.Document_ID GROUP BY d.Document_ID, d.Document_Name;	cre_Doc_Template_Mgt
SELECT Document_ID FROM Paragraphs GROUP BY Document_ID HAVING COUNT(Paragraph_ID) >= 2;	cre_Doc_Template_Mgt
SELECT Document_ID FROM Paragraphs GROUP BY Document_ID HAVING COUNT(Paragraph_ID) >= 2;	cre_Doc_Template_Mgt
SELECT D.Document_ID, D.Document_Name FROM Documents D JOIN Paragraphs P ON D.Document_ID = P.Document_ID GROUP BY D.Document_ID, D.Document_Name ORDER BY COUNT(P.Paragraph_ID) DESC LIMIT 1;	cre_Doc_Template_Mgt
SELECT D.Document_ID, D.Document_Name FROM Documents AS D JOIN Paragraphs AS P ON D.Document_ID = P.Document_ID GROUP BY D.Document_ID, D.Document_Name ORDER BY COUNT(P.Paragraph_ID) DESC LIMIT 1;	cre_Doc_Template_Mgt
SELECT Document_ID FROM Paragraphs GROUP BY Document_ID ORDER BY COUNT(*) ASC LIMIT 1;	cre_Doc_Template_Mgt
SELECT Document_ID FROM Paragraphs GROUP BY Document_ID ORDER BY COUNT(*) ASC LIMIT 1;	cre_Doc_Template_Mgt
SELECT Document_ID FROM Paragraphs GROUP BY Document_ID HAVING COUNT(Paragraph_ID) BETWEEN 1 AND 2;	cre_Doc_Template_Mgt
SELECT Document_ID FROM Paragraphs GROUP BY Document_ID HAVING COUNT(Paragraph_ID) BETWEEN 1 AND 2;	cre_Doc_Template_Mgt
SELECT D.Document_ID FROM Documents D JOIN Paragraphs P ON D.Document_ID = P.Document_ID WHERE P.Paragraph_Text = 'Brazil' INTERSECT SELECT D.Document_ID FROM Documents D JOIN Paragraphs P ON D.Document_ID = P.Document_ID WHERE P.Paragraph_Text = 'Ireland';	cre_Doc_Template_Mgt
SELECT T1.document_id FROM Documents AS T1 JOIN Paragraphs AS T2 ON T1.document_id = T2.document_id WHERE T2.Paragraph_Text LIKE '%Brazil%' INTERSECT SELECT T1.document_id FROM Documents AS T1 JOIN Paragraphs AS T2 ON T1.document_id = T2.document_id WHERE T2.Paragraph_Text LIKE '%Ireland%';	cre_Doc_Template_Mgt
SELECT COUNT(*) FROM teacher;	course_teach
SELECT COUNT(*) FROM teacher;	course_teach
SELECT Name FROM teacher ORDER BY Age ASC;	course_teach
SELECT Name FROM teacher ORDER BY Age ASC;	course_teach
SELECT Age, Hometown FROM teacher;	course_teach
SELECT Age, Hometown FROM teacher;	course_teach
SELECT Name FROM teacher WHERE Hometown != 'Little Lever Urban District';	course_teach
SELECT Name FROM teacher WHERE Hometown != 'Little Lever Urban District'	course_teach
SELECT Name FROM teacher WHERE Age = 32 OR Age = 33;	course_teach
SELECT Name FROM teacher WHERE Age IN ('32', '33');	course_teach
SELECT Hometown FROM teacher ORDER BY Age ASC LIMIT 1;	course_teach
SELECT Hometown FROM teacher ORDER BY Age ASC LIMIT 1;	course_teach
SELECT Hometown, COUNT(*) FROM teacher GROUP BY Hometown;	course_teach
SELECT Hometown, COUNT(*) FROM teacher GROUP BY Hometown;	course_teach
SELECT Hometown FROM teacher GROUP BY Hometown ORDER BY COUNT(*) DESC LIMIT 1;	course_teach
SELECT Hometown FROM teacher GROUP BY Hometown ORDER BY COUNT(*) DESC LIMIT 1;	course_teach
SELECT Hometown FROM teacher GROUP BY Hometown HAVING COUNT(*) >= 2;	course_teach
SELECT Hometown FROM teacher GROUP BY Hometown HAVING COUNT(*) >= 2;	course_teach
SELECT T2.Name, T3.Course FROM course_arrange AS T1 JOIN teacher AS T2 ON T1.Teacher_ID = T2.Teacher_ID JOIN course AS T3 ON T1.Course_ID = T3.Course_ID;	course_teach
SELECT T2.Name, T3.Course FROM course_arrange AS T1 JOIN teacher AS T2 ON T1.Teacher_ID = T2.Teacher_ID JOIN course AS T3 ON T1.Course_ID = T3.Course_ID;	course_teach
SELECT teacher.Name, course.Course FROM course_arrange JOIN teacher ON course_arrange.Teacher_ID = teacher.Teacher_ID JOIN course ON course_arrange.Course_ID = course.Course_ID ORDER BY teacher.Name ASC;	course_teach
SELECT teacher.Name, course.Course FROM course_arrange JOIN teacher ON course_arrange.Teacher_ID = teacher.Teacher_ID JOIN course ON course_arrange.Course_ID = course.Course_ID ORDER BY teacher.Name ASC;	course_teach
SELECT T2.Name FROM course_arrange AS T1 JOIN teacher AS T2 ON T1.Teacher_ID = T2.Teacher_ID JOIN course AS T3 ON T1.Course_ID = T3.Course_ID WHERE T3.Course = "Math";	course_teach
SELECT T.Name FROM teacher AS T JOIN course_arrange AS CA ON T.Teacher_ID = CA.Teacher_ID JOIN course AS C ON CA.Course_ID = C.Course_ID WHERE C.Course LIKE '%math%';	course_teach
SELECT T2.Name, COUNT(T1.Course_ID) FROM course_arrange AS T1 JOIN teacher AS T2 ON T1.Teacher_ID = T2.Teacher_ID GROUP BY T2.Name;	course_teach
SELECT T2.Name, COUNT(T1.Course_ID) AS Course_Count FROM course_arrange AS T1 JOIN teacher AS T2 ON T1.Teacher_ID = T2.Teacher_ID GROUP BY T2.Name;	course_teach
SELECT T2.Name FROM course_arrange AS T1 JOIN teacher AS T2 ON T1.Teacher_ID = T2.Teacher_ID GROUP BY T1.Teacher_ID HAVING COUNT(DISTINCT T1.Course_ID) >= 2;	course_teach
SELECT T2.Name FROM course_arrange AS T1 JOIN teacher AS T2 ON T1.Teacher_ID = T2.Teacher_ID GROUP BY T1.Teacher_ID HAVING COUNT(DISTINCT T1.Course_ID) >= 2;	course_teach
SELECT Name FROM teacher WHERE Teacher_ID NOT IN (SELECT Teacher_ID FROM course_arrange)	course_teach
SELECT Name FROM teacher WHERE Teacher_ID NOT IN (SELECT Teacher_ID FROM course_arrange)	course_teach
SELECT COUNT(*) FROM visitor WHERE Age < 30;	museum_visit
SELECT Name FROM visitor WHERE Level_of_membership > 4 ORDER BY Level_of_membership DESC;	museum_visit
SELECT AVG(Age) FROM visitor WHERE Level_of_membership <= 4;	museum_visit
SELECT Name, Level_of_membership FROM visitor WHERE Level_of_membership >4ORDER BY Age DESC;	museum_visit
SELECT Museum_ID, Name FROM museum ORDER BY Num_of_Staff DESC LIMIT 1;	museum_visit
SELECT AVG(Num_of_Staff) FROM museum WHERE Open_Year < 2009;	museum_visit
SELECT Num_of_Staff, Open_Year FROM museum WHERE Name = 'Plaza Museum';	museum_visit
SELECT Name FROM museum WHERE Num_of_Staff > (SELECT MIN(Num_of_Staff) FROM museum WHERE Open_Year > 2010)	museum_visit
SELECT T2.ID, T2.Name, T2.Age FROM visit AS T1 JOIN visitor AS T2 ON T1.visitor_ID = T2.ID GROUP BY T1.visitor_ID HAVING COUNT(T1.Museum_ID) > 1;	museum_visit
SELECT v.ID, v.Name, v.Level_of_membership FROM visitor v JOIN visit vi ON v.ID = vi.visitor_ID GROUP BY v.ID, v.Name, v.Level_of_membership ORDER BY SUM(vi.Total_spent) DESC LIMIT 1;	museum_visit
SELECT T1.Museum_ID, T1.Name FROM museum AS T1 JOIN visit AS T2 ON T1.Museum_ID = T2.Museum_ID GROUP BY T1.Museum_ID ORDER BY COUNT(*) DESC LIMIT 1;	museum_visit
SELECT Name FROM museum WHERE Museum_ID NOT IN (SELECT Museum_ID FROM visit)	museum_visit
SELECT v.Name, v.Age FROM visitor v JOIN visit vi ON v.ID = vi.visitor_ID ORDER BY vi.Num_of_Ticket DESC LIMIT 1;	museum_visit
SELECT avg(Num_of_Ticket) , max(Num_of_Ticket) FROM visit;	museum_visit
SELECT SUM(Total_spent) FROM visit JOIN visitor ON visit.visitor_ID = visitor.ID WHERE visitor.Level_of_membership = 1;	museum_visit
SELECT v.Name FROM visitor v JOIN visit vi ON v.ID = vi.visitor_ID JOIN museum m ON vi.Museum_ID = m.Museum_ID WHERE m.Open_Year <2009 INTERSECT SELECT v.Name FROM visitor v JOIN visit vi ON v.ID = vi.visitor_ID JOIN museum m ON vi.Museum_ID = m.Museum_ID WHERE m.Open_Year > 2011;	museum_visit
SELECT COUNT(*) FROM visitor WHERE ID NOT IN ( SELECT visitor_ID FROM visit WHERE Museum_ID IN ( SELECT Museum_ID FROM museum WHERE Open_Year >2010 ) );	museum_visit
SELECT COUNT(*) FROM museum WHERE Open_Year > 2013 OR Open_Year < 2008;	museum_visit
SELECT COUNT(*) FROM players;	wta_1
SELECT count(*) FROM players;	wta_1
SELECT COUNT(*) FROM matches;	wta_1
SELECT COUNT(*) FROM matches;	wta_1
SELECT first_name, birth_date FROM players WHERE country_code = 'USA';	wta_1
SELECT first_name, birth_date FROM players WHERE country_code = 'USA';	wta_1
SELECT AVG(loser_age) AS average_loser_age, AVG(winner_age) AS average_winner_age FROM matches;	wta_1
SELECT AVG(loser_age) AS average_loser_age, AVG(winner_age) AS average_winner_age FROM matches;	wta_1
SELECT AVG(winner_rank) FROM matches;	wta_1
SELECT AVG(winner_rank) FROM matches;	wta_1
SELECT MIN(loser_rank) FROM matches;	wta_1
SELECT MIN(loser_rank) AS best_loser_rank FROM matches;	wta_1
SELECT COUNT(DISTINCT country_code) FROM players;	wta_1
SELECT COUNT(DISTINCT country_code) FROM players;	wta_1
SELECT COUNT(DISTINCT loser_name) FROM matches;	wta_1
SELECT COUNT(DISTINCT loser_name) FROM matches;	wta_1
SELECT tourney_name FROM matches GROUP BY tourney_name HAVING COUNT(*) > 10;	wta_1
SELECT tourney_name FROM matches GROUP BY tourney_name HAVING COUNT(*) > 10;	wta_1
SELECT DISTINCT winner_name FROM matches WHERE year =2013 INTERSECT SELECT DISTINCT winner_name FROM matches WHERE year = 2016;	wta_1
SELECT DISTINCT T1.first_name, T1.last_name FROM players AS T1 JOIN matches AS T2 ON T1.player_id = T2.winner_id WHERE T2.tourney_id IN ('2013-W-WT-TUR-01A-2013', '2016-1049');	wta_1
SELECT COUNT(*) FROM matches WHERE year IN (2013, 2016);	wta_1
SELECT COUNT(*) FROM matches WHERE year IN (2013, 2016);	wta_1
SELECT DISTINCT p.country_code, p.first_name FROM players p JOIN matches m ON p.player_id = m.winner_id WHERE m.tourney_name = 'WTA Championships' INTERSECT SELECT DISTINCT p.country_code, p.first_name FROM players p JOIN matches m ON p.player_id = m.winner_id WHERE m.tourney_name = 'Australian Open';	wta_1
SELECT T1.first_name, T1.country_code FROM players AS T1 JOIN matches AS T2 ON T1.player_id = T2.winner_id WHERE T2.tourney_name = 'WTA Championships' INTERSECT SELECT T1.first_name, T1.country_code FROM players AS T1 JOIN matches AS T2 ON T1.player_id = T2.winner_id WHERE T2.tourney_name = 'Australian Open';	wta_1
SELECT first_name, country_code FROM players ORDER BY birth_date ASC LIMIT 1;	wta_1
SELECT first_name, country_code FROM players ORDER BY birth_date ASC LIMIT 1;	wta_1
SELECT first_name, last_name FROM players WHERE hand = 'L' ORDER BY birth_date;	wta_1
SELECT first_name, last_name FROM players WHERE hand = 'Left' ORDER BY birth_date;	wta_1
SELECT T1.first_name, T1.country_code FROM players AS T1 JOIN rankings AS T2 ON T1.player_id = T2.player_id GROUP BY T1.player_id ORDER BY SUM(T2.tours) DESC LIMIT 1;	wta_1
SELECT T1.first_name, T1.country_code FROM players AS T1 JOIN rankings AS T2 ON T1.player_id = T2.player_id GROUP BY T1.player_id ORDER BY SUM(T2.tours) DESC LIMIT 1;	wta_1
SELECT year FROM matches GROUP BY year ORDER BY COUNT(*) DESC LIMIT 1;	wta_1
SELECT year FROM matches GROUP BY year ORDER BY COUNT(*) DESC LIMIT 1;	wta_1
SELECT T1.first_name, T1.last_name, T3.ranking_points FROM players AS T1 JOIN matches AS T2 ON T1.player_id = T2.winner_id JOIN rankings AS T3 ON T1.player_id = T3.player_id GROUP BY T2.winner_id ORDER BY COUNT(*) DESC LIMIT 1;	wta_1
SELECT p.first_name, p.last_name, r.ranking_points FROM players p JOIN ( SELECT winner_id, COUNT(*) as wins FROM matches GROUP BY winner_id ORDER BY wins DESC LIMIT 1 ) m ON p.player_id = m.winner_id JOIN rankings r ON p.player_id = r.player_id ORDER BY r.ranking_points DESC LIMIT 1;	wta_1
SELECT T2.first_name, T2.last_name FROM matches AS T1 JOIN players AS T2 ON T1.winner_id = T2.player_id WHERE T1.tourney_name = 'Australian Open' ORDER BY T1.winner_rank_points DESC LIMIT 1;	wta_1
SELECT T3.first_name, T3.last_name FROM matches AS T1 JOIN players AS T3 ON T1.winner_id = T3.player_id WHERE T1.tourney_name = 'Australian Open' ORDER BY T1.winner_rank_points DESC LIMIT 1;	wta_1
SELECT m.loser_name, m.winner_name FROM matches m ORDER BY m.minutes DESC LIMIT 1;	wta_1
SELECT T2.first_name || ' ' || T2.last_name AS winner_name, T3.first_name || ' ' || T3.last_name AS loser_name FROM matches AS T1 JOIN players AS T2 ON T1.winner_id = T2.player_id JOIN players AS T3 ON T1.loser_id = T3.player_id ORDER BY T1.minutes DESC LIMIT 1;	wta_1
SELECT p.first_name, AVG(r.ranking) AS average_ranking FROM players p JOIN rankings r ON p.player_id = r.player_id GROUP BY p.player_id, p.first_name;	wta_1
SELECT p.first_name, AVG(r.ranking) AS average_ranking FROM players p JOIN rankings r ON p.player_id = r.player_id GROUP BY p.first_name;	wta_1
SELECT p.first_name, SUM(r.ranking_points) AS total_ranking_points FROM players p JOIN rankings r ON p.player_id = r.player_id GROUP BY p.player_id, p.first_name;	wta_1
SELECT p.first_name, SUM(r.ranking_points) AS total_ranking_points FROM players p JOIN rankings r ON p.player_id = r.player_id GROUP BY p.first_name;	wta_1
SELECT country_code, COUNT(*) FROM players GROUP BY country_code;	wta_1
SELECT country_code, COUNT(*) FROM players GROUP BY country_code;	wta_1
SELECT country_code FROM players GROUP BY country_code ORDER BY COUNT(*) DESC LIMIT 1;	wta_1
SELECT country_code FROM players GROUP BY country_code ORDER BY COUNT(*) DESC LIMIT 1;	wta_1
SELECT country_code FROM players GROUP BY country_code HAVING COUNT(*) > 50;	wta_1
SELECT country_code FROM players GROUP BY country_code HAVING COUNT(*) > 50;	wta_1
SELECT ranking_date, SUM(tours) AS total_tours FROM rankings GROUP BY ranking_date;	wta_1
SELECT ranking_date, SUM(tours) AS total_tours FROM rankings GROUP BY ranking_date;	wta_1
SELECT COUNT(*), year FROM matches GROUP BY year;	wta_1
SELECT year, COUNT(*) AS number_of_matches FROM matches GROUP BY year;	wta_1
SELECT T1.first_name, T1.last_name, T2.winner_rank FROM players AS T1 JOIN matches AS T2 ON T1.player_id = T2.winner_id ORDER BY T2.winner_age ASC LIMIT 3;	wta_1
SELECT T2.first_name, T2.last_name, T1.winner_rank FROM matches AS T1 JOIN players AS T2 ON T1.winner_id = T2.player_id ORDER BY T2.birth_date DESC LIMIT 3;	wta_1
SELECT COUNT(DISTINCT p.player_id) FROM players p JOIN matches m ON p.player_id = m.winner_id WHERE m.tourney_name = 'WTA Championships' AND p.hand = 'Left';	wta_1
SELECT COUNT(DISTINCT winner_id) FROM matches WHERE tourney_name = 'WTA Championships' AND winner_hand = 'L';	wta_1
SELECT p.first_name, p.country_code, p.birth_date FROM players p JOIN ( SELECT player_id, MAX(ranking_points) as max_points FROM rankings GROUP BY player_id ) r ON p.player_id = r.player_id ORDER BY r.max_points DESC LIMIT 1;	wta_1
SELECT p.first_name, p.country_code, p.birth_date FROM players p JOIN matches m ON p.player_id = m.winner_id GROUP BY p.player_id ORDER BY SUM(m.winner_rank_points) DESC LIMIT 1;	wta_1
SELECT hand, COUNT(*) FROM players GROUP BY hand;	wta_1
SELECT hand, COUNT(*) FROM players GROUP BY hand;	wta_1
SELECT COUNT(*) FROM ship WHERE disposition_of_ship = 'Captured';	battle_death
SELECT name, tonnage FROM ship ORDER BY name DESC;	battle_death
SELECT name, date, result FROM battle;	battle_death
SELECT max(killed) AS max_killed, min(killed) AS min_killed FROM death;	battle_death
SELECT AVG(injured) FROM death;	battle_death
SELECT death.killed, death.injured FROM death JOIN ship ON death.caused_by_ship_id = ship.id WHERE ship.tonnage = 't';	battle_death
SELECT name, result FROM battle WHERE bulgarian_commander != 'Boril';	battle_death
SELECT DISTINCT T1.id, T1.name FROM battle AS T1 JOIN ship AS T2 ON T1.id = T2.lost_in_battle WHERE T2.ship_type = 'Brig';	battle_death
SELECT b.id, b.name FROM battle b JOIN ship s ON b.id = s.lost_in_battle JOIN death d ON s.id = d.caused_by_ship_id GROUP BY b.id, b.name HAVING SUM(d.killed) > 10;	battle_death
SELECT T1.id, T1.name FROM ship AS T1 JOIN death AS T2 ON T1.id = T2.caused_by_ship_id GROUP BY T1.id, T1.name ORDER BY SUM(T2.injured) DESC LIMIT 1;	battle_death
SELECT DISTINCT name FROM battle WHERE bulgarian_commander = 'Kaloyan' AND latin_commander = 'Baldwin I';	battle_death
SELECT COUNT(DISTINCT result) FROM battle;	battle_death
SELECT COUNT(*) FROM battle WHERE id NOT IN ( SELECT lost_in_battle FROM ship WHERE tonnage = '225' );	battle_death
SELECT b.name, b.date FROM battle b JOIN ship s ON b.id = s.lost_in_battle WHERE s.name IN ('Lettice', 'HMS Atalanta') GROUP BY b.name, b.date HAVING COUNT(DISTINCT s.name) = 2;	battle_death
SELECT name, result, bulgarian_commander FROM battle WHERE id NOT IN (SELECT lost_in_battle FROM ship WHERE location = 'English Channel');	battle_death
SELECT note FROM death WHERE note LIKE '%East%';	battle_death
SELECT line_1, line_2 FROM Addresses;	student_transcripts_tracking
SELECT line_1, line_2 FROM Addresses;	student_transcripts_tracking
SELECT count(*) FROM Courses;	student_transcripts_tracking
SELECT count(*) FROM Courses;	student_transcripts_tracking
SELECT course_description FROM Courses WHERE course_name LIKE '%Math%';	student_transcripts_tracking
SELECT course_description FROM Courses WHERE course_name LIKE "%math%";	student_transcripts_tracking
SELECT zip_postcode FROM Addresses WHERE city = 'Port Chelsea';	student_transcripts_tracking
SELECT zip_postcode FROM Addresses WHERE city = 'Port Chelsea';	student_transcripts_tracking
SELECT D.department_name, D.department_id FROM Degree_Programs DP JOIN Departments D ON DP.department_id = D.department_id GROUP BY D.department_id ORDER BY COUNT(DP.degree_program_id) DESC LIMIT 1;	student_transcripts_tracking
SELECT T2.department_name, T2.department_id FROM Degree_Programs AS T1 JOIN Departments AS T2 ON T1.department_id = T2.department_id GROUP BY T2.department_id ORDER BY COUNT(*) DESC LIMIT 1;	student_transcripts_tracking
SELECT COUNT(DISTINCT department_name) FROM Degree_Programs JOIN Departments ON Degree_Programs.department_id = Departments.department_id;	student_transcripts_tracking
SELECT COUNT(DISTINCT department_name) FROM Degree_Programs JOIN Departments ON Degree_Programs.department_id = Departments.department_id;	student_transcripts_tracking
SELECT COUNT(DISTINCT department_name) FROM Degree_Programs JOIN Departments ON Degree_Programs.department_id = Departments.department_id;	student_transcripts_tracking
SELECT COUNT(DISTINCT degree_program_id) FROM Degree_Programs;	student_transcripts_tracking
SELECT COUNT(*) FROM Degree_Programs dp JOIN Departments d ON dp.department_id = d.department_id WHERE d.department_name = 'engineer';	student_transcripts_tracking
SELECT COUNT(*) FROM Degree_Programs JOIN Departments ON Degree_Programs.department_id = Departments.department_id WHERE Departments.department_name = 'engineer';	student_transcripts_tracking
SELECT section_name, section_description FROM Sections;	student_transcripts_tracking
SELECT section_name, section_description FROM Sections;	student_transcripts_tracking
SELECT c.course_name, c.course_id FROM Courses c JOIN Sections s ON c.course_id = s.course_id GROUP BY c.course_id, c.course_name HAVING COUNT(s.section_id) <= 2;	student_transcripts_tracking
SELECT c.course_name, c.course_id FROM Courses AS c LEFT JOIN Sections AS s ON c.course_id = s.course_id GROUP BY c.course_id HAVING COUNT(s.section_id) < 2;	student_transcripts_tracking
SELECT section_name FROM Sections ORDER BY section_name DESC;	student_transcripts_tracking
SELECT section_name FROM Sections ORDER BY section_name DESC;	student_transcripts_tracking
SELECT T2.semester_name, T2.semester_id FROM Student_Enrolment AS T1 JOIN Semesters AS T2 ON T1.semester_id = T2.semester_id GROUP BY T2.semester_id ORDER BY COUNT(T1.student_id) DESC LIMIT 1;	student_transcripts_tracking
SELECT S.semester_id, S.semester_name FROM Semesters S JOIN ( SELECT semester_id, COUNT(student_id) as student_count FROM Student_Enrolment GROUP BY semester_id ) SE ON S.semester_id = SE.semester_id WHERE SE.student_count = ( SELECT MAX(student_count) FROM ( SELECT COUNT(student_id) as student_count FROM Student_Enrolment GROUP BY semester_id ) );	student_transcripts_tracking
SELECT department_description FROM Departments WHERE department_name LIKE '%computer%';	student_transcripts_tracking
SELECT T1.department_description FROM Departments AS T1 JOIN Degree_Programs AS T2 ON T1.department_id = T2.department_id WHERE T1.department_name LIKE '%computer%';	student_transcripts_tracking
SELECT S.first_name, S.middle_name, S.last_name, S.student_id FROM Students S JOIN Student_Enrolment SE ON S.student_id = SE.student_id GROUP BY S.student_id, S.first_name, S.middle_name, S.last_name, SE.semester_id HAVING COUNT(DISTINCT SE.degree_program_id) = 2;	student_transcripts_tracking
SELECT T2.first_name, T2.middle_name, T2.last_name, T2.student_id FROM Student_Enrolment AS T1 JOIN Students AS T2 ON T1.student_id = T2.student_id GROUP BY T1.student_id, T1.semester_id HAVING COUNT(DISTINCT T1.degree_program_id) = 2;	student_transcripts_tracking
SELECT Students.first_name, Students.middle_name, Students.last_name FROM Students JOIN Student_Enrolment ON Students.student_id = Student_Enrolment.student_id JOIN Degree_Programs ON Student_Enrolment.degree_program_id = Degree_Programs.degree_program_id WHERE Degree_Programs.degree_summary_name LIKE '%Bachelor%';	student_transcripts_tracking
SELECT T3.first_name, T3.middle_name, T3.last_name FROM Student_Enrolment AS T1 JOIN Degree_Programs AS T2 ON T1.degree_program_id = T2.degree_program_id JOIN Students AS T3 ON T1.student_id = T3.student_id WHERE T2.degree_summary_name LIKE '%Bachelor%';	student_transcripts_tracking
SELECT degree_summary_name FROM Student_Enrolment JOIN Degree_Programs ON Student_Enrolment.degree_program_id = Degree_Programs.degree_program_id GROUP BY degree_summary_name ORDER BY COUNT(student_id) DESC LIMIT 1;	student_transcripts_tracking
SELECT dp.degree_summary_name FROM Student_Enrolment se JOIN Degree_Programs dp ON se.degree_program_id = dp.degree_program_id GROUP BY dp.degree_summary_name ORDER BY COUNT(se.student_id) DESC LIMIT 1;	student_transcripts_tracking
SELECT degree_program_id, degree_summary_name FROM Degree_Programs WHERE degree_program_id = ( SELECT degree_program_id FROM Student_Enrolment GROUP BY degree_program_id ORDER BY COUNT(student_id) DESC LIMIT 1 );	student_transcripts_tracking
SELECT T2.degree_program_id, T2.degree_summary_name FROM Student_Enrolment AS T1 JOIN Degree_Programs AS T2 ON T1.degree_program_id = T2.degree_program_id GROUP BY T2.degree_program_id ORDER BY COUNT(T1.student_id) DESC LIMIT 1;	student_transcripts_tracking
SELECT T1.student_id, T2.first_name, T2.middle_name, T2.last_name, COUNT(T1.student_enrolment_id) AS number_of_enrollments FROM Student_Enrolment AS T1 JOIN Students AS T2 ON T1.student_id = T2.student_id GROUP BY T1.student_id ORDER BY number_of_enrollments DESC LIMIT 1;	student_transcripts_tracking
SELECT T2.first_name, T2.middle_name, T2.last_name, T1.student_id, COUNT(T1.student_enrolment_id) AS num_enrollments FROM Student_Enrolment AS T1 JOIN Students AS T2 ON T1.student_id = T2.student_id GROUP BY T1.student_id ORDER BY num_enrollments DESC LIMIT 1;	student_transcripts_tracking
SELECT semester_name FROM Semesters WHERE semester_id NOT IN (SELECT semester_id FROM Student_Enrolment);	student_transcripts_tracking
SELECT semester_name FROM Semesters WHERE semester_id NOT IN (SELECT semester_id FROM Student_Enrolment);	student_transcripts_tracking
SELECT DISTINCT T1.course_name FROM Courses AS T1 JOIN Student_Enrolment_Courses AS T2 ON T1.course_id = T2.course_id;	student_transcripts_tracking
SELECT DISTINCT T1.course_name FROM Courses AS T1 JOIN Student_Enrolment_Courses AS T2 ON T1.course_id = T2.course_id;	student_transcripts_tracking
SELECT T1.course_name FROM Courses AS T1 JOIN Student_Enrolment_Courses AS T2 ON T1.course_id = T2.course_id GROUP BY T1.course_id ORDER BY count(*) DESC LIMIT 1;	student_transcripts_tracking
SELECT c.course_name FROM Courses c JOIN Student_Enrolment_Courses sec ON c.course_id = sec.course_id GROUP BY c.course_name ORDER BY COUNT(sec.student_enrolment_id) DESC LIMIT 1;	student_transcripts_tracking
SELECT last_name FROM Students WHERE current_address_id IN ( SELECT address_id FROM Addresses WHERE state_province_county = "North Carolina" ) AND student_id NOT IN ( SELECT student_id FROM Student_Enrolment )	student_transcripts_tracking
SELECT last_name FROM Students WHERE current_address_id IN ( SELECT address_id FROM Addresses WHERE state_province_county = 'North Carolina' ) AND student_id NOT IN ( SELECT student_id FROM Student_Enrolment )	student_transcripts_tracking
SELECT T1.transcript_date, T1.transcript_id FROM Transcripts AS T1 JOIN Transcript_Contents AS T2 ON T1.transcript_id = T2.transcript_id GROUP BY T1.transcript_id HAVING COUNT(T2.student_course_id) >= 2;	student_transcripts_tracking
SELECT T.transcript_date, T.transcript_id FROM Transcripts T JOIN Transcript_Contents TC ON T.transcript_id = TC.transcript_id GROUP BY T.transcript_id HAVING COUNT(TC.student_course_id) >= 2;	student_transcripts_tracking
SELECT cell_mobile_number FROM Students WHERE first_name = 'Timmothy' AND last_name = 'Ward';	student_transcripts_tracking
SELECT cell_mobile_number FROM Students WHERE first_name = 'Timmothy' AND last_name = 'Ward';	student_transcripts_tracking
SELECT first_name, middle_name, last_name FROM Students ORDER BY date_first_registered ASC LIMIT 1;	student_transcripts_tracking
SELECT first_name, middle_name, last_name FROM Students ORDER BY date_first_registered ASC LIMIT 1;	student_transcripts_tracking
SELECT first_name, middle_name, last_name FROM Students ORDER BY date_left ASC LIMIT 1;	student_transcripts_tracking
SELECT first_name, middle_name, last_name FROM Students ORDER BY date_left ASC LIMIT 1;	student_transcripts_tracking
SELECT T2.first_name FROM Addresses AS T1 JOIN Students AS T2 ON T1.address_id = T2.permanent_address_id JOIN Addresses AS T3 ON T3.address_id = T2.current_address_id WHERE T1.line_1 != T3.line_1 OR T1.line_2 != T3.line_2 OR T1.line_3 != T3.line_3 OR T1.city != T3.city OR T1.zip_postcode != T3.zip_postcode OR T1.state_province_county != T3.state_province_county OR T1.country != T3.country;	student_transcripts_tracking
SELECT s.first_name FROM Students s JOIN Addresses a1 ON s.permanent_address_id = a1.address_id JOIN Addresses a2 ON s.current_address_id = a2.address_id WHERE a1.address_id <> a2.address_id;	student_transcripts_tracking
SELECT T1.address_id, T1.line_1, T1.line_2, T1.line_3 FROM Addresses AS T1 JOIN Students AS T2 ON T1.address_id = T2.current_address_id GROUP BY T1.address_id ORDER BY COUNT(T2.student_id) DESC LIMIT 1;	student_transcripts_tracking
SELECT T1.address_id, T1.line_1, T1.line_2 FROM Addresses AS T1 JOIN Students AS T2 ON T1.address_id = T2.permanent_address_id GROUP BY T1.address_id ORDER BY COUNT(T2.student_id) DESC LIMIT 1;	student_transcripts_tracking
SELECT AVG(transcript_date) FROM Transcripts;	student_transcripts_tracking
SELECT AVG(transcript_date) FROM Transcripts;	student_transcripts_tracking
SELECT T1.transcript_date, T1.other_details FROM Transcripts AS T1 JOIN Transcript_Contents AS T2 ON T1.transcript_id = T2.transcript_id ORDER BY T1.transcript_date ASC LIMIT 1;	student_transcripts_tracking
SELECT transcript_date, other_details FROM Transcripts ORDER BY transcript_date ASC LIMIT 1;	student_transcripts_tracking
SELECT COUNT(*) FROM Transcripts;	student_transcripts_tracking
SELECT COUNT(*) FROM Transcripts;	student_transcripts_tracking
SELECT transcript_date FROM Transcripts ORDER BY transcript_date DESC LIMIT 1;	student_transcripts_tracking
SELECT transcript_date FROM Transcripts ORDER BY transcript_date DESC LIMIT 1;	student_transcripts_tracking
SELECT student_course_id, COUNT(transcript_id) AS transcript_count FROM Transcript_Contents GROUP BY student_course_id ORDER BY transcript_count DESC LIMIT 1;	student_transcripts_tracking
SELECT T3.student_enrolment_id, COUNT(T1.student_course_id) as course_count FROM Transcript_Contents AS T1 JOIN Student_Enrolment_Courses AS T2 ON T1.student_course_id = T2.student_course_id JOIN Student_Enrolment AS T3 ON T2.student_enrolment_id = T3.student_enrolment_id GROUP BY T3.student_enrolment_id ORDER BY course_count DESC LIMIT 1;	student_transcripts_tracking
SELECT T.transcript_date, T.transcript_id FROM Transcripts T JOIN Transcript_Contents TC ON T.transcript_id = TC.transcript_id GROUP BY T.transcript_id ORDER BY COUNT(*) ASC LIMIT 1;	student_transcripts_tracking
SELECT T1.transcript_date, T1.transcript_id FROM Transcripts AS T1 JOIN Transcript_Contents AS T2 ON T1.transcript_id = T2.transcript_id GROUP BY T1.transcript_id ORDER BY COUNT(T2.student_course_id) ASC LIMIT 1;	student_transcripts_tracking
SELECT s.semester_name FROM Semesters s JOIN Student_Enrolment se ON s.semester_id = se.semester_id JOIN Degree_Programs dp ON se.degree_program_id = dp.degree_program_id WHERE dp.degree_summary_name IN ('Master', 'Bachelor') GROUP BY s.semester_name HAVING COUNT(DISTINCT dp.degree_summary_name) = 2;	student_transcripts_tracking
SELECT semester_id FROM Student_Enrolment JOIN Degree_Programs ON Student_Enrolment.degree_program_id = Degree_Programs.degree_program_id WHERE degree_summary_name = 'Masters' INTERSECT SELECT semester_id FROM Student_Enrolment JOIN Degree_Programs ON Student_Enrolment.degree_program_id = Degree_Programs.degree_program_id WHERE degree_summary_name = 'Bachelors';	student_transcripts_tracking
SELECT COUNT(DISTINCT T1.current_address_id) FROM Students AS T1;	student_transcripts_tracking
SELECT DISTINCT line_1, line_2, line_3, city, zip_postcode, state_province_county, country FROM Addresses WHERE address_id IN (SELECT current_address_id FROM Students UNION SELECT permanent_address_id FROM Students);	student_transcripts_tracking
SELECT other_student_details FROM Students ORDER BY other_student_details DESC;	student_transcripts_tracking
SELECT other_student_details FROM Students ORDER BY last_name DESC, first_name DESC;	student_transcripts_tracking
SELECT section_description FROM Sections WHERE section_name = "h";	student_transcripts_tracking
SELECT section_description FROM Sections WHERE section_name = "h";	student_transcripts_tracking
SELECT first_name FROM Students WHERE permanent_address_id IN (SELECT address_id FROM Addresses WHERE country = 'Haiti') OR cell_mobile_number = '09700166582';	student_transcripts_tracking
SELECT first_name FROM Students WHERE permanent_address_id IN (SELECT address_id FROM Addresses WHERE country = 'Haiti') OR cell_mobile_number = '09700166582';	student_transcripts_tracking
SELECT Title FROM Cartoon ORDER BY Title;	tvshow
SELECT Title FROM Cartoon ORDER BY Title;	tvshow
SELECT Title FROM Cartoon WHERE Directed_by = 'Ben Jones';	tvshow
SELECT Title FROM Cartoon WHERE Directed_by = 'Ben Jones';	tvshow
SELECT COUNT(*) FROM Cartoon WHERE Written_by = 'Joseph Kuhr';	tvshow
SELECT COUNT(*) FROM Cartoon WHERE Written_by = 'Joseph Kuhr';	tvshow
SELECT Title, Directed_by FROM Cartoon ORDER BY Original_air_date;	tvshow
SELECT Title, Directed_by FROM Cartoon ORDER BY Original_air_date;	tvshow
SELECT Title FROM Cartoon WHERE Directed_by = 'Ben Jones' OR Directed_by = 'Brandon Vietti';	tvshow
SELECT Title FROM Cartoon WHERE Directed_by = 'Ben Jones' OR Directed_by = 'Brandon Vietti';	tvshow
SELECT T1.Country, COUNT(T1.id) AS Number_of_TV_Channels FROM TV_Channel AS T1 GROUP BY T1.Country ORDER BY Number_of_TV_Channels DESC LIMIT 1;	tvshow
SELECT Country, COUNT(*) AS ChannelCount FROM TV_Channel GROUP BY Country ORDER BY ChannelCount DESC LIMIT 1;	tvshow
SELECT COUNT(DISTINCT series_name), COUNT(DISTINCT Content) FROM TV_Channel;	tvshow
SELECT COUNT(DISTINCT series_name), COUNT(DISTINCT Content) FROM TV_Channel;	tvshow
SELECT Content FROM TV_Channel WHERE series_name = 'Sky Radio';	tvshow
SELECT Content FROM TV_Channel WHERE series_name = 'Sky Radio';	tvshow
SELECT Package_Option FROM TV_Channel WHERE series_name = 'Sky Radio';	tvshow
SELECT Package_Option FROM TV_Channel WHERE series_name = 'Sky Radio';	tvshow
SELECT COUNT(*) FROM TV_Channel WHERE Language = 'English';	tvshow
SELECT COUNT(*) FROM TV_Channel WHERE Language = 'English';	tvshow
SELECT Language, COUNT(*) AS Number_of_TV_Channels FROM TV_Channel GROUP BY Language ORDER BY Number_of_TV_Channels ASC LIMIT 1;	tvshow
SELECT Language, COUNT(*) AS Channel_Count FROM TV_Channel GROUP BY Language ORDER BY Channel_Count ASC LIMIT 1;	tvshow
SELECT Language, COUNT(*) FROM TV_Channel GROUP BY Language;	tvshow
SELECT Language, COUNT(*) FROM TV_Channel GROUP BY Language;	tvshow
SELECT TV_Channel.series_name FROM Cartoon JOIN TV_Channel ON Cartoon.Channel = TV_Channel.id WHERE Cartoon.Title = 'The Rise of the Blue Beetle!';	tvshow
SELECT T3.series_name FROM Cartoon AS T1 JOIN TV_Channel AS T3 ON T1.Channel = T3.id WHERE T1.Title = 'The Rise of the Blue Beetle!';	tvshow
SELECT Cartoon.Title FROM Cartoon JOIN TV_Channel ON Cartoon.Channel = TV_Channel.id WHERE TV_Channel.series_name = 'Sky Radio';	tvshow
SELECT Cartoon.Title FROM Cartoon JOIN TV_Channel ON Cartoon.Channel = TV_Channel.id WHERE TV_Channel.series_name = 'Sky Radio';	tvshow
SELECT Episode FROM TV_series ORDER BY Rating;	tvshow
SELECT Episode FROM TV_series ORDER BY Rating;	tvshow
SELECT Episode, Rating FROM TV_series ORDER BY Rating DESC LIMIT 3;	tvshow
SELECT Episode, Rating FROM TV_series ORDER BY Rating DESC LIMIT 3;	tvshow
SELECT min(Share) , max(Share) FROM TV_series;	tvshow
SELECT max(Share) , min(Share) FROM TV_series;	tvshow
SELECT Air_Date FROM TV_series WHERE Episode = 'A Love of a Lifetime';	tvshow
SELECT Air_Date FROM TV_series WHERE Episode = 'A Love of a Lifetime';	tvshow
SELECT Weekly_Rank FROM TV_series WHERE Episode = 'A Love of a Lifetime';	tvshow
SELECT Weekly_Rank FROM TV_series WHERE Episode = 'A Love of a Lifetime';	tvshow
SELECT T2.series_name FROM TV_series AS T1 JOIN TV_Channel AS T2 ON T1.Channel = T2.id WHERE T1.Episode = 'A Love of a Lifetime';	tvshow
SELECT T2.series_name FROM TV_series AS T1 JOIN TV_Channel AS T2 ON T1.Channel = T2.id WHERE T1.Episode = 'A Love of a Lifetime';	tvshow
SELECT T1.Episode FROM TV_series AS T1 JOIN TV_Channel AS T2 ON T1.Channel = T2.id WHERE T2.series_name = 'Sky Radio';	tvshow
SELECT T1.Episode FROM TV_series AS T1 JOIN TV_Channel AS T2 ON T1.Channel = T2.id WHERE T2.series_name = 'Sky Radio';	tvshow
SELECT directed_by, COUNT(*) AS number_of_cartoons FROM Cartoon GROUP BY directed_by;	tvshow
SELECT Directed_by, COUNT(*) FROM Cartoon GROUP BY Directed_by;	tvshow
SELECT Production_code, Channel FROM Cartoon ORDER BY Original_air_date DESC LIMIT 1;	tvshow
SELECT Production_code, Channel FROM Cartoon ORDER BY Original_air_date DESC LIMIT 1;	tvshow
SELECT Package_Option, series_name FROM TV_Channel WHERE Hight_definition_TV = 'Yes';	tvshow
SELECT Package_Option, series_name FROM TV_Channel WHERE Hight_definition_TV = 'Yes';	tvshow
SELECT DISTINCT T3.Country FROM Cartoon AS T1 JOIN TV_Channel AS T3 ON T1.Channel = T3.id WHERE T1.Written_by = 'Todd Casey';	tvshow
SELECT DISTINCT T2.Country FROM Cartoon AS T1 JOIN TV_Channel AS T2 ON T1.Channel = T2.id WHERE T1.Written_by = 'Todd Casey';	tvshow
SELECT Country FROM TV_Channel WHERE id NOT IN (SELECT Channel FROM Cartoon WHERE Written_by = 'Todd Casey')	tvshow
SELECT Country FROM TV_Channel WHERE id NOT IN (SELECT Channel FROM Cartoon WHERE Written_by = 'Todd Casey')	tvshow
SELECT DISTINCT T3.series_name, T3.Country FROM Cartoon AS T1 JOIN TV_Channel AS T3 ON T1.Channel = T3.id WHERE T1.Directed_by IN ('Ben Jones', 'Michael Chang');	tvshow
SELECT DISTINCT T3.series_name, T3.Country FROM Cartoon AS T1 JOIN TV_Channel AS T3 ON T1.Channel = T3.id WHERE T1.Directed_by = 'Ben Jones' INTERSECT SELECT DISTINCT T3.series_name, T3.Country FROM Cartoon AS T1 JOIN TV_Channel AS T3 ON T1.Channel = T3.id WHERE T1.Directed_by = 'Michael Chang';	tvshow
SELECT Pixel_aspect_ratio_PAR, Country FROM TV_Channel WHERE Language != "english";	tvshow
SELECT Pixel_aspect_ratio_PAR, Country FROM TV_Channel WHERE Language != 'English';	tvshow
SELECT id FROM TV_Channel WHERE Country IN ( SELECT Country FROM TV_Channel GROUP BY Country HAVING COUNT(*) > 2 )	tvshow
SELECT Channel FROM TV_series GROUP BY Channel HAVING COUNT(*) > 2;	tvshow
SELECT id FROM TV_Channel WHERE id NOT IN (SELECT Channel FROM Cartoon WHERE Directed_by = 'Ben Jones')	tvshow
SELECT id FROM TV_Channel EXCEPT SELECT Channel FROM Cartoon WHERE Directed_by = 'Ben Jones'	tvshow
SELECT Package_Option FROM TV_Channel WHERE id NOT IN (SELECT Channel FROM Cartoon WHERE Directed_by = 'Ben Jones');	tvshow
SELECT Package_Option FROM TV_Channel WHERE id NOT IN (SELECT Channel FROM Cartoon WHERE Directed_by = 'Ben Jones');	tvshow
SELECT count(*) FROM poker_player;	poker_player
SELECT COUNT(*) FROM poker_player;	poker_player
SELECT Earnings FROM poker_player ORDER BY Earnings DESC;	poker_player
SELECT Earnings FROM poker_player ORDER BY Earnings DESC;	poker_player
SELECT Final_Table_Made, Best_Finish FROM poker_player;	poker_player
SELECT Final_Table_Made, Best_Finish FROM poker_player;	poker_player
SELECT AVG(Earnings) FROM poker_player;	poker_player
SELECT AVG(Earnings) FROM poker_player;	poker_player
SELECT Money_Rank FROM poker_player ORDER BY Earnings DESC LIMIT 1;	poker_player
SELECT Money_Rank FROM poker_player ORDER BY Earnings DESC LIMIT 1;	poker_player
SELECT MAX(Final_Table_Made) FROM poker_player WHERE Earnings < 200000;	poker_player
SELECT MAX(Final_Table_Made) FROM poker_player WHERE Earnings < 200000;	poker_player
SELECT T2.Name FROM poker_player AS T1 JOIN people AS T2 ON T1.People_ID = T2.People_ID;	poker_player
SELECT T2.Name FROM poker_player AS T1 JOIN people AS T2 ON T1.People_ID = T2.People_ID;	poker_player
SELECT T2.Name FROM poker_player AS T1 JOIN people AS T2 ON T1.People_ID = T2.People_ID WHERE T1.Earnings > 300000;	poker_player
SELECT T2.Name FROM poker_player AS T1 JOIN people AS T2 ON T1.People_ID = T2.People_ID WHERE T1.Earnings > 300000;	poker_player
SELECT T2.Name FROM poker_player AS T1 JOIN people AS T2 ON T1.People_ID = T2.People_ID ORDER BY T1.Final_Table_Made ASC;	poker_player
SELECT T2.Name FROM poker_player AS T1 JOIN people AS T2 ON T1.People_ID = T2.People_ID ORDER BY T1.Final_Table_Made ASC;	poker_player
SELECT T2.Birth_Date FROM poker_player AS T1 JOIN people AS T2 ON T1.People_ID = T2.People_ID ORDER BY T1.Earnings ASC LIMIT 1;	poker_player
SELECT T2.Birth_Date FROM poker_player AS T1 JOIN people AS T2 ON T1.People_ID = T2.People_ID ORDER BY T1.Earnings ASC LIMIT 1;	poker_player
SELECT T1.Money_Rank FROM poker_player AS T1 JOIN people AS T2 ON T1.People_ID = T2.People_ID ORDER BY T2.Height DESC LIMIT 1;	poker_player
SELECT T1.Money_Rank FROM poker_player AS T1 JOIN people AS T2 ON T1.People_ID = T2.People_ID ORDER BY T2.Height DESC LIMIT 1;	poker_player
SELECT AVG(Earnings) FROM poker_player JOIN people ON poker_player.People_ID = people.People_ID WHERE Height > 200;	poker_player
SELECT AVG(Earnings) FROM poker_player JOIN people ON poker_player.People_ID = people.People_ID WHERE people.Height > 200;	poker_player
SELECT T2.Name FROM poker_player AS T1 JOIN people AS T2 ON T1.People_ID = T2.People_ID ORDER BY T1.Earnings DESC;	poker_player
SELECT T2.Name FROM poker_player AS T1 JOIN people AS T2 ON T1.People_ID = T2.People_ID ORDER BY T1.Earnings DESC;	poker_player
SELECT Nationality, COUNT(*) FROM people GROUP BY Nationality;	poker_player
SELECT Nationality, COUNT(*) FROM people GROUP BY Nationality;	poker_player
SELECT Nationality FROM people GROUP BY Nationality ORDER BY COUNT(*) DESC LIMIT 1;	poker_player
SELECT Nationality FROM people GROUP BY Nationality ORDER BY COUNT(*) DESC LIMIT 1;	poker_player
SELECT Nationality FROM people GROUP BY Nationality HAVING COUNT(*) >= 2;	poker_player
SELECT Nationality FROM people GROUP BY Nationality HAVING COUNT(*) >= 2;	poker_player
SELECT Name, Birth_Date FROM people ORDER BY Name ASC;	poker_player
SELECT Name, Birth_Date FROM people ORDER BY Name;	poker_player
SELECT Name FROM people WHERE Nationality != 'Russia';	poker_player
SELECT Name FROM people WHERE Nationality != 'Russia';	poker_player
SELECT Name FROM people WHERE People_ID NOT IN (SELECT People_ID FROM poker_player);	poker_player
SELECT Name FROM people WHERE People_ID NOT IN (SELECT People_ID FROM poker_player);	poker_player
SELECT COUNT(DISTINCT Nationality) FROM people;	poker_player
SELECT COUNT(DISTINCT Nationality) FROM people;	poker_player
SELECT COUNT(DISTINCT state) FROM AREA_CODE_STATE;	voter_1
SELECT contestant_number, contestant_name FROM CONTESTANTS ORDER BY contestant_name DESC;	voter_1
SELECT vote_id, phone_number, state FROM VOTES;	voter_1
SELECT max(area_code), min(area_code) FROM AREA_CODE_STATE;	voter_1
SELECT MAX(created) FROM VOTES WHERE state = 'CA';	voter_1
SELECT contestant_name FROM CONTESTANTS WHERE contestant_name != 'Jessie Alloway';	voter_1
SELECT DISTINCT state, created FROM VOTES;	voter_1
SELECT C.contestant_number, C.contestant_name FROM CONTESTANTS C JOIN VOTES V ON C.contestant_number = V.contestant_number GROUP BY C.contestant_number, C.contestant_name HAVING COUNT(V.vote_id) >= 2;	voter_1
SELECT T1.contestant_number, T1.contestant_name FROM CONTESTANTS AS T1 JOIN VOTES AS T2 ON T1.contestant_number = T2.contestant_number GROUP BY T1.contestant_number, T1.contestant_name ORDER BY COUNT(*) ASC LIMIT 1;	voter_1
SELECT COUNT(*) FROM VOTES WHERE state IN ('NY', 'CA');	voter_1
SELECT contestant_number FROM CONTESTANTS EXCEPT SELECT contestant_number FROM VOTES;	voter_1
SELECT T1.area_code FROM AREA_CODE_STATE AS T1 JOIN VOTES AS T2 ON T1.state = T2.state GROUP BY T1.area_code ORDER BY COUNT(*) DESC LIMIT 1;	voter_1
SELECT V.created, V.state, V.phone_number FROM VOTES V JOIN CONTESTANTS C ON V.contestant_number = C.contestant_number WHERE C.contestant_name = 'Tabatha Gehling';	voter_1
SELECT DISTINCT a.area_code FROM VOTES v1 JOIN AREA_CODE_STATE a ON v1.state = a.state JOIN CONTESTANTS c1 ON v1.contestant_number = c1.contestant_number WHERE c1.contestant_name = 'Tabatha Gehling' INTERSECT SELECT DISTINCT a.area_code FROM VOTES v2 JOIN AREA_CODE_STATE a ON v2.state = a.state JOIN CONTESTANTS c2 ON v2.contestant_number = c2.contestant_number WHERE c2.contestant_name = 'Kelly Clauss';	voter_1
SELECT contestant_name FROM CONTESTANTS WHERE contestant_name LIKE '%Al%';	voter_1
SELECT Name FROM country WHERE IndepYear > 1950;	world_1
SELECT Name FROM country WHERE IndepYear > 1950;	world_1
SELECT COUNT(*) FROM country WHERE GovernmentForm = 'Republic';	world_1
SELECT COUNT(*) FROM country WHERE GovernmentForm = 'Republic';	world_1
SELECT SUM(SurfaceArea) FROM country WHERE Region = 'Caribbean';	world_1
SELECT SUM(SurfaceArea) FROM country WHERE Region = 'Caribbean';	world_1
SELECT Continent FROM country WHERE Name = 'Anguilla';	world_1
SELECT Continent FROM country WHERE Name = 'Anguilla';	world_1
SELECT T2.Region FROM city AS T1 JOIN country AS T2 ON T1.CountryCode = T2.Code WHERE T1.Name = 'Kabul';	world_1
SELECT T1.Region FROM country AS T1 JOIN city AS T2 ON T1.Code = T2.CountryCode WHERE T2.Name = 'Kabul';	world_1
SELECT Language FROM countrylanguage JOIN country ON countrylanguage.CountryCode = country.Code WHERE country.Name = 'Aruba' ORDER BY Percentage DESC LIMIT 1;	world_1
SELECT T2.Language FROM country AS T1 JOIN countrylanguage AS T2 ON T1.Code = T2.CountryCode WHERE T1.Name = 'Aruba' ORDER BY T2.Percentage DESC LIMIT 1;	world_1
SELECT Population, LifeExpectancy FROM country WHERE Name = "Brazil";	world_1
SELECT Population, LifeExpectancy FROM country WHERE Name = 'Brazil';	world_1
SELECT Region, Population FROM country WHERE Name = 'Angola';	world_1
SELECT Continent, Population FROM country WHERE Name = 'Angola';	world_1
SELECT AVG(LifeExpectancy) FROM country WHERE Region = 'Central Africa';	world_1
SELECT AVG(LifeExpectancy) FROM country WHERE Region = 'Central Africa';	world_1
SELECT Name FROM country WHERE Continent = 'Asia' ORDER BY LifeExpectancy ASC LIMIT 1;	world_1
SELECT Name FROM country WHERE Continent = 'Asia' ORDER BY LifeExpectancy ASC LIMIT 1;	world_1
SELECT SUM(Population), MAX(GNP) FROM country WHERE Continent = 'Asia';	world_1
SELECT SUM(Population) AS TotalPopulation, MAX(GNP) AS LargestGNP FROM country WHERE Continent = 'Asia';	world_1
SELECT AVG(LifeExpectancy) FROM country WHERE Continent = 'Africa' AND GovernmentForm = 'Republic';	world_1
SELECT AVG(LifeExpectancy) FROM country WHERE Continent = 'Africa' AND GovernmentForm = 'Republic';	world_1
SELECT SUM(SurfaceArea) FROM country WHERE Continent IN ('Asia', 'Europe');	world_1
SELECT SUM(SurfaceArea) FROM country WHERE Continent IN ('Asia', 'Europe');	world_1
SELECT SUM(Population) FROM city WHERE District = 'Gelderland';	world_1
SELECT SUM(Population) FROM city WHERE District = 'Gelderland';	world_1
SELECT AVG(GNP), SUM(Population) FROM country WHERE GovernmentForm = 'US Territory';	world_1
SELECT AVG(GNP), SUM(Population) FROM country WHERE GovernmentForm = 'US Territory';	world_1
SELECT COUNT(DISTINCT Language) FROM countrylanguage;	world_1
SELECT COUNT(DISTINCT Language) FROM countrylanguage;	world_1
SELECT COUNT(DISTINCT GovernmentForm) FROM country WHERE Continent = 'Africa';	world_1
SELECT COUNT(DISTINCT GovernmentForm) FROM country WHERE Continent = 'Africa';	world_1
SELECT COUNT(DISTINCT Language) FROM countrylanguage JOIN country ON countrylanguage.CountryCode = country.Code WHERE country.Name = 'Aruba';	world_1
SELECT COUNT(DISTINCT Language) FROM countrylanguage JOIN country ON countrylanguage.CountryCode = country.Code WHERE country.Name = 'Aruba';	world_1
SELECT COUNT(*) FROM countrylanguage AS T1 JOIN country AS T2 ON T1.CountryCode = T2.Code WHERE T2.Name = 'Afghanistan' AND T1.IsOfficial = 'T';	world_1
SELECT COUNT(*) FROM countrylanguage AS T1 JOIN country AS T2 ON T1.CountryCode = T2.Code WHERE T2.Name = 'Afghanistan' AND T1.IsOfficial = 'T';	world_1
SELECT T.Name FROM country AS T JOIN countrylanguage AS CL ON T.Code = CL.CountryCode GROUP BY T.Name ORDER BY COUNT(DISTINCT CL.Language) DESC LIMIT 1;	world_1
SELECT c.Name FROM country c JOIN countrylanguage cl ON c.Code = cl.CountryCode GROUP BY c.Name ORDER BY COUNT(cl.Language) DESC LIMIT 1;	world_1
SELECT Continent FROM country JOIN countrylanguage ON country.Code = countrylanguage.CountryCode GROUP BY Continent ORDER BY COUNT(DISTINCT Language) DESC LIMIT 1;	world_1
SELECT Continent FROM country JOIN countrylanguage ON country.Code = countrylanguage.CountryCode GROUP BY Continent ORDER BY COUNT(DISTINCT Language) DESC LIMIT 1;	world_1
SELECT COUNT(DISTINCT T1.Code) FROM country AS T1 JOIN countrylanguage AS T2 ON T1.Code = T2.CountryCode JOIN countrylanguage AS T3 ON T1.Code = T3.CountryCode WHERE T2.Language = 'English' AND T3.Language = 'Dutch';	world_1
SELECT COUNT(DISTINCT T1.Code) FROM country AS T1 JOIN countrylanguage AS T2 ON T1.Code = T2.CountryCode WHERE T2.Language = 'English' INTERSECT SELECT COUNT(DISTINCT T1.Code) FROM country AS T1 JOIN countrylanguage AS T2 ON T1.Code = T2.CountryCode WHERE T2.Language = 'Dutch';	world_1
SELECT c.Name FROM country c JOIN countrylanguage cl1 ON c.Code = cl1.CountryCode JOIN countrylanguage cl2 ON c.Code = cl2.CountryCode WHERE cl1.Language = 'English' AND cl2.Language = 'French';	world_1
SELECT c.Name FROM country c JOIN countrylanguage cl1 ON c.Code = cl1.CountryCode JOIN countrylanguage cl2 ON c.Code = cl2.CountryCode WHERE cl1.Language = 'English' AND cl2.Language = 'French';	world_1
SELECT c.Name FROM country c JOIN countrylanguage cl1 ON c.Code = cl1.CountryCode AND cl1.Language = 'English' AND cl1.IsOfficial = 'T' JOIN countrylanguage cl2 ON c.Code = cl2.CountryCode AND cl2.Language = 'French' AND cl2.IsOfficial = 'T';	world_1
SELECT c.Name FROM country c JOIN countrylanguage cl1 ON c.Code = cl1.CountryCode JOIN countrylanguage cl2 ON c.Code = cl2.CountryCode WHERE cl1.Language = 'English' AND cl1.IsOfficial = 'T' AND cl2.Language = 'French' AND cl2.IsOfficial = 'T';	world_1
SELECT COUNT(DISTINCT c.Continent) FROM country c JOIN countrylanguage cl ON c.Code = cl.CountryCode WHERE cl.Language = 'Chinese';	world_1
SELECT Continent, COUNT(DISTINCT CountryCode) AS NumberOfCountries FROM countrylanguage JOIN country ON countrylanguage.CountryCode = country.Code WHERE Language = 'Chinese' GROUP BY Continent;	world_1
SELECT DISTINCT T1.Region FROM country AS T1 JOIN countrylanguage AS T2 ON T1.Code = T2.CountryCode WHERE T2.Language = 'English' OR T2.Language = 'Dutch';	world_1
SELECT DISTINCT T1.Region FROM country AS T1 JOIN countrylanguage AS T2 ON T1.Code = T2.CountryCode WHERE T2.Language IN ('Dutch', 'English');	world_1
SELECT c.Name FROM country c JOIN countrylanguage cl ON c.Code = cl.CountryCode WHERE (cl.Language = 'English' OR cl.Language = 'Dutch') AND cl.IsOfficial = 'T';	world_1
SELECT DISTINCT c.Name FROM country c JOIN countrylanguage cl ON c.Code = cl.CountryCode WHERE (cl.Language = 'English' OR cl.Language = 'Dutch') AND cl.IsOfficial = 'T';	world_1
SELECT cl.Language FROM countrylanguage cl JOIN country c ON cl.CountryCode = c.Code WHERE c.Continent = 'Asia' GROUP BY cl.Language ORDER BY SUM(cl.Percentage * c.Population) DESC LIMIT 1;	world_1
SELECT Language FROM countrylanguage JOIN country ON countrylanguage.CountryCode = country.Code WHERE Continent = 'Asia' GROUP BY Language ORDER BY COUNT(DISTINCT CountryCode) DESC LIMIT 1;	world_1
SELECT Language FROM countrylanguage WHERE CountryCode IN ( SELECT Code FROM country WHERE GovernmentForm = 'Republic' ) GROUP BY Language HAVING COUNT(CountryCode) = 1;	world_1
SELECT Language FROM countrylanguage JOIN country ON countrylanguage.CountryCode = country.Code WHERE GovernmentForm = 'Republic' GROUP BY Language HAVING COUNT(DISTINCT country.Code) = 1;	world_1
SELECT c.Name FROM city c JOIN countrylanguage cl ON c.CountryCode = cl.CountryCode WHERE cl.Language = 'English' ORDER BY c.Population DESC LIMIT 1;	world_1
SELECT c.Name FROM city c JOIN countrylanguage cl ON c.CountryCode = cl.CountryCode WHERE cl.Language = 'English' ORDER BY c.Population DESC LIMIT 1;	world_1
SELECT Name, Population, LifeExpectancy FROM country WHERE Continent = 'Asia' ORDER BY SurfaceArea DESC LIMIT 1;	world_1
SELECT Name, Population, LifeExpectancy FROM country WHERE Continent = 'Asia' ORDER BY SurfaceArea DESC LIMIT 1;	world_1
SELECT AVG(LifeExpectancy) FROM country WHERE Code NOT IN ( SELECT CountryCode FROM countrylanguage WHERE Language = 'English' AND IsOfficial = 'T' )	world_1
SELECT AVG(LifeExpectancy) FROM country WHERE Code NOT IN ( SELECT CountryCode FROM countrylanguage WHERE Language = 'English' AND IsOfficial = 'T' )	world_1
SELECT SUM(Population) FROM country WHERE Code NOT IN (SELECT CountryCode FROM countrylanguage WHERE Language = 'English');	world_1
SELECT SUM(T1.Population) FROM country AS T1 WHERE T1.Code NOT IN (SELECT T2.CountryCode FROM countrylanguage AS T2 WHERE T2.Language = 'English')	world_1
SELECT Language FROM countrylanguage JOIN country ON countrylanguage.CountryCode = country.Code WHERE country.HeadOfState = 'Beatrix' AND countrylanguage.IsOfficial = 'T';	world_1
SELECT Language FROM countrylanguage JOIN country ON countrylanguage.CountryCode = country.Code WHERE country.HeadOfState = 'Beatrix' AND countrylanguage.IsOfficial = 'T';	world_1
SELECT COUNT(DISTINCT T2.Language) FROM country AS T1 JOIN countrylanguage AS T2 ON T1.Code = T2.CountryCode WHERE T1.IndepYear <1930 AND T2.IsOfficial = 'T';	world_1
SELECT COUNT(DISTINCT T2.Language) FROM country AS T1 JOIN countrylanguage AS T2 ON T1.Code = T2.CountryCode WHERE T1.IndepYear <1930 AND T2.IsOfficial = 'T';	world_1
SELECT Name FROM country WHERE SurfaceArea > (SELECT MAX(SurfaceArea) FROM country WHERE Continent = 'Europe')	world_1
SELECT Name FROM country WHERE SurfaceArea > (SELECT MAX(SurfaceArea) FROM country WHERE Continent = 'Europe')	world_1
SELECT Name FROM country WHERE Continent = 'Africa' AND Population < (SELECT MIN(Population) FROM country WHERE Continent = 'Asia');	world_1
SELECT Name FROM country WHERE Continent = 'Africa' AND Population < (SELECT MIN(Population) FROM country WHERE Continent = 'Asia')	world_1
SELECT Name FROM country WHERE Continent = 'Asia' AND Population > (SELECT MAX(Population) FROM country WHERE Continent = 'Africa')	world_1
SELECT Name FROM country WHERE Continent = 'Asia' AND Population > (SELECT MAX(Population) FROM country WHERE Continent = 'Africa')	world_1
SELECT Code FROM country WHERE Code NOT IN (SELECT CountryCode FROM countrylanguage WHERE Language = 'English')	world_1
SELECT Code FROM country WHERE Code NOT IN (SELECT CountryCode FROM countrylanguage WHERE Language = 'English')	world_1
SELECT DISTINCT CountryCode FROM countrylanguage WHERE Language != 'English';	world_1
SELECT Code FROM country WHERE Code NOT IN ( SELECT CountryCode FROM countrylanguage WHERE Language = 'English' )	world_1
SELECT Code FROM country WHERE Code NOT IN (SELECT CountryCode FROM countrylanguage WHERE Language = 'English') AND GovernmentForm != 'Republic';	world_1
SELECT Code FROM country WHERE Code NOT IN (SELECT CountryCode FROM countrylanguage WHERE Language = 'English') AND GovernmentForm != 'Republic';	world_1
SELECT T1.Name FROM city AS T1 JOIN country AS T2 ON T1.CountryCode = T2.Code WHERE T2.Continent = 'Europe' AND T2.Code NOT IN ( SELECT CountryCode FROM countrylanguage WHERE Language = 'English' AND IsOfficial = 'T' )	world_1
SELECT c.Name FROM city AS c JOIN country AS co ON c.CountryCode = co.Code WHERE co.Continent = 'Europe' AND c.CountryCode NOT IN ( SELECT cl.CountryCode FROM countrylanguage AS cl WHERE cl.Language = 'English' AND cl.IsOfficial = 'T' )	world_1
SELECT DISTINCT T1.Name FROM city AS T1 JOIN country AS T2 ON T1.CountryCode = T2.Code JOIN countrylanguage AS T3 ON T2.Code = T3.CountryCode WHERE T2.Continent = 'Asia' AND T3.Language = 'Chinese' AND T3.IsOfficial = 'T';	world_1
SELECT DISTINCT c.Name FROM city c JOIN country co ON c.CountryCode = co.Code JOIN countrylanguage cl ON co.Code = cl.CountryCode WHERE co.Continent = 'Asia' AND cl.Language = 'Chinese' AND cl.IsOfficial = 'T';	world_1
SELECT Name, IndepYear, SurfaceArea FROM country ORDER BY Population ASC LIMIT 1;	world_1
SELECT Name, IndepYear, SurfaceArea FROM country ORDER BY Population ASC LIMIT 1;	world_1
SELECT Population, Name, HeadOfState FROM country ORDER BY SurfaceArea DESC LIMIT 1;	world_1
SELECT Name, Population, HeadOfState FROM country ORDER BY SurfaceArea DESC LIMIT 1;	world_1
SELECT c.Name, COUNT(cl.Language) AS NumberOfLanguages FROM country c JOIN countrylanguage cl ON c.Code = cl.CountryCode GROUP BY c.Name HAVING COUNT(cl.Language) >= 3;	world_1
SELECT c.Name, COUNT(cl.Language) AS LanguageCount FROM country c JOIN countrylanguage cl ON c.Code = cl.CountryCode GROUP BY c.Name HAVING COUNT(cl.Language) > 2;	world_1
SELECT District, COUNT(*) FROM city WHERE Population > (SELECT AVG(Population) FROM city) GROUP BY District;	world_1
SELECT District, COUNT(*) FROM city WHERE Population > (SELECT AVG(Population) FROM city) GROUP BY District;	world_1
SELECT c.GovernmentForm, SUM(c.Population) AS TotalPopulation FROM country c GROUP BY c.GovernmentForm HAVING AVG(c.LifeExpectancy) > 72;	world_1
SELECT c.GovernmentForm, SUM(c.Population) AS TotalPopulation FROM country c GROUP BY c.GovernmentForm HAVING AVG(c.LifeExpectancy) > 72;	world_1
SELECT Continent, AVG(LifeExpectancy) AS AverageLifeExpectancy, SUM(Population) AS TotalPopulation FROM country GROUP BY Continent HAVING AVG(LifeExpectancy) < 72;	world_1
SELECT Continent, SUM(Population) AS TotalPopulation, AVG(LifeExpectancy) AS AverageLifeExpectancy FROM country GROUP BY Continent HAVING AVG(LifeExpectancy) < 72;	world_1
SELECT Name, SurfaceArea FROM country ORDER BY SurfaceArea DESC LIMIT 5;	world_1
SELECT Name, SurfaceArea FROM country ORDER BY SurfaceArea DESC LIMIT 5;	world_1
SELECT Name FROM country ORDER BY Population DESC LIMIT 3;	world_1
SELECT Name FROM country ORDER BY Population DESC LIMIT 3;	world_1
SELECT Name FROM country ORDER BY Population ASC LIMIT 3;	world_1
SELECT Name FROM country ORDER BY Population ASC LIMIT 3;	world_1
SELECT COUNT(*) FROM country WHERE Continent = 'Asia';	world_1
SELECT COUNT(*) FROM country WHERE Continent = 'Asia';	world_1
SELECT Name FROM country WHERE Continent = 'Europe' AND Population = 80000;	world_1
SELECT Name FROM country WHERE Continent = 'Europe' AND Population = 80000;	world_1
SELECT SUM(Population), AVG(SurfaceArea) FROM country WHERE Continent = 'North America' AND SurfaceArea > 3000;	world_1
SELECT SUM(Population), AVG(SurfaceArea) FROM country WHERE Continent = 'North America' AND SurfaceArea > 3000;	world_1
SELECT Name FROM city WHERE Population BETWEEN 160000 AND 900000;	world_1
SELECT Name FROM city WHERE Population BETWEEN 160000 AND 900000;	world_1
SELECT Language FROM countrylanguage GROUP BY Language ORDER BY COUNT(CountryCode) DESC LIMIT 1;	world_1
SELECT Language FROM countrylanguage GROUP BY Language ORDER BY COUNT(CountryCode) DESC LIMIT 1;	world_1
SELECT c.Name, cl.Language, cl.Percentage FROM country c JOIN ( SELECT CountryCode, MAX(Percentage) AS MaxPercentage FROM countrylanguage GROUP BY CountryCode ) max_cl ON c.Code = max_cl.CountryCode JOIN countrylanguage cl ON c.Code = cl.CountryCode AND cl.Percentage = max_cl.MaxPercentage;	world_1
SELECT cl.CountryCode, cl.Language FROM countrylanguage cl JOIN ( SELECT CountryCode, MAX(Percentage) AS MaxPercentage FROM countrylanguage GROUP BY CountryCode ) max_cl ON cl.CountryCode = max_cl.CountryCode AND cl.Percentage = max_cl.MaxPercentage;	world_1
SELECT COUNT(*) FROM countrylanguage cl JOIN country c ON cl.CountryCode = c.Code WHERE cl.Language = 'Spanish' AND cl.Percentage = ( SELECT MAX(cl2.Percentage) FROM countrylanguage cl2 WHERE cl2.CountryCode = cl.CountryCode AND cl2.Language = 'Spanish' );	world_1
SELECT COUNT(DISTINCT cl.CountryCode) FROM countrylanguage cl WHERE cl.Language = 'Spanish' AND cl.Percentage > 50;	world_1
SELECT CountryCode FROM countrylanguage WHERE Language = 'Spanish' ORDER BY Percentage DESC LIMIT 1;	world_1
SELECT CountryCode FROM countrylanguage WHERE Language = 'Spanish' AND Percentage = (SELECT MAX(Percentage) FROM countrylanguage WHERE CountryCode = countrylanguage.CountryCode);	world_1
SELECT COUNT(*) FROM conductor;	orchestra
SELECT COUNT(*) FROM conductor;	orchestra
SELECT Name FROM conductor ORDER BY Age ASC;	orchestra
SELECT Name FROM conductor ORDER BY Age;	orchestra
SELECT Name FROM conductor WHERE Nationality != 'USA';	orchestra
SELECT Name FROM conductor WHERE Nationality != 'USA';	orchestra
SELECT Record_Company FROM orchestra ORDER BY Year_of_Founded DESC;	orchestra
SELECT Record_Company FROM orchestra ORDER BY Year_of_Founded DESC;	orchestra
SELECT AVG(Attendance) FROM show;	orchestra
SELECT AVG(Attendance) FROM show;	orchestra
SELECT max(Share), min(Share) FROM performance WHERE Type != 'Live final';	orchestra
SELECT max(Share), min(Share) FROM performance WHERE Type != 'Live final';	orchestra
SELECT COUNT(DISTINCT Nationality) FROM conductor;	orchestra
SELECT COUNT(DISTINCT Nationality) FROM conductor;	orchestra
SELECT Name FROM conductor ORDER BY Year_of_Work DESC;	orchestra
SELECT Name FROM conductor ORDER BY Year_of_Work DESC;	orchestra
SELECT Name FROM conductor ORDER BY Year_of_Work DESC LIMIT 1;	orchestra
SELECT Name FROM conductor ORDER BY Year_of_Work DESC LIMIT 1;	orchestra
SELECT conductor.Name, orchestra.Orchestra FROM conductor JOIN orchestra ON conductor.Conductor_ID = orchestra.Conductor_ID;	orchestra
SELECT conductor.Name, orchestra.Orchestra FROM conductor JOIN orchestra ON conductor.Conductor_ID = orchestra.Conductor_ID;	orchestra
SELECT c.Name FROM conductor c JOIN orchestra o ON c.Conductor_ID = o.Conductor_ID GROUP BY c.Conductor_ID HAVING COUNT(DISTINCT o.Orchestra_ID) > 1;	orchestra
SELECT c.Name FROM conductor c JOIN orchestra o ON c.Conductor_ID = o.Conductor_ID GROUP BY c.Conductor_ID HAVING COUNT(DISTINCT o.Orchestra_ID) > 1;	orchestra
SELECT c.Name FROM conductor c JOIN orchestra o ON c.Conductor_ID = o.Conductor_ID GROUP BY c.Conductor_ID ORDER BY COUNT(o.Orchestra_ID) DESC LIMIT 1;	orchestra
SELECT c.Name FROM conductor c JOIN orchestra o ON c.Conductor_ID = o.Conductor_ID GROUP BY c.Conductor_ID ORDER BY COUNT(DISTINCT o.Orchestra) DESC LIMIT 1;	orchestra
SELECT conductor.Name FROM conductor JOIN orchestra ON conductor.Conductor_ID = orchestra.Conductor_ID WHERE orchestra.Year_of_Founded > 2008;	orchestra
SELECT conductor.Name FROM conductor JOIN orchestra ON conductor.Conductor_ID = orchestra.Conductor_ID WHERE orchestra.Year_of_Founded > 2008;	orchestra
SELECT Record_Company, COUNT(*) FROM orchestra GROUP BY Record_Company;	orchestra
SELECT Record_Company, COUNT(*) AS NumberOfOrchestras FROM orchestra GROUP BY Record_Company;	orchestra
SELECT Major_Record_Format FROM orchestra GROUP BY Major_Record_Format ORDER BY COUNT(*) ASC;	orchestra
SELECT Major_Record_Format FROM orchestra GROUP BY Major_Record_Format ORDER BY COUNT(*) DESC;	orchestra
SELECT Record_Company FROM orchestra GROUP BY Record_Company ORDER BY COUNT(*) DESC LIMIT 1;	orchestra
SELECT Record_Company FROM orchestra GROUP BY Record_Company ORDER BY COUNT(*) DESC LIMIT 1;	orchestra
SELECT Orchestra FROM orchestra WHERE Orchestra_ID NOT IN (SELECT Orchestra_ID FROM performance)	orchestra
SELECT Orchestra FROM orchestra WHERE Orchestra_ID NOT IN (SELECT Orchestra_ID FROM performance)	orchestra
SELECT Record_Company FROM orchestra WHERE Year_of_Founded <2003 INTERSECT SELECT Record_Company FROM orchestra WHERE Year_of_Founded > 2003;	orchestra
SELECT Record_Company FROM orchestra WHERE Year_of_Founded <2003 INTERSECT SELECT Record_Company FROM orchestra WHERE Year_of_Founded > 2003;	orchestra
SELECT COUNT(*) FROM orchestra WHERE Major_Record_Format IN ('CD', 'DVD');	orchestra
SELECT COUNT(*) FROM orchestra WHERE Major_Record_Format IN ('CD', 'DVD');	orchestra
SELECT DISTINCT o.Year_of_Founded FROM orchestra o JOIN performance p ON o.Orchestra_ID = p.Orchestra_ID GROUP BY o.Orchestra_ID HAVING COUNT(p.Performance_ID) > 1;	orchestra
SELECT orchestra.Year_of_Founded FROM orchestra JOIN performance ON orchestra.Orchestra_ID = performance.Orchestra_ID GROUP BY orchestra.Orchestra_ID HAVING COUNT(performance.Performance_ID) > 1;	orchestra
SELECT COUNT(*) FROM Highschooler;	network_1
SELECT count(*) FROM Highschooler;	network_1
SELECT name, grade FROM Highschooler;	network_1
SELECT name, grade FROM Highschooler;	network_1
SELECT DISTINCT grade FROM Highschooler;	network_1
SELECT grade FROM Highschooler;	network_1
SELECT grade FROM Highschooler WHERE name = 'Kyle';	network_1
SELECT grade FROM Highschooler WHERE name = 'Kyle';	network_1
SELECT name FROM Highschooler WHERE grade = 10;	network_1
SELECT name FROM Highschooler WHERE grade = 10;	network_1
SELECT ID FROM Highschooler WHERE name = 'Kyle';	network_1
SELECT ID FROM Highschooler WHERE name = "Kyle";	network_1
SELECT COUNT(*) FROM Highschooler WHERE grade IN (9, 10);	network_1
SELECT COUNT(*) FROM Highschooler WHERE grade IN (9, 10);	network_1
SELECT grade, COUNT(*) FROM Highschooler GROUP BY grade;	network_1
SELECT grade, COUNT(*) FROM Highschooler GROUP BY grade;	network_1
SELECT grade FROM Highschooler GROUP BY grade ORDER BY COUNT(*) DESC LIMIT 1;	network_1
SELECT grade FROM Highschooler GROUP BY grade ORDER BY count(*) DESC LIMIT 1;	network_1
SELECT grade FROM Highschooler GROUP BY grade HAVING COUNT(*) >= 4;	network_1
SELECT grade FROM Highschooler GROUP BY grade HAVING COUNT(*) >= 4;	network_1
SELECT student_id, COUNT(friend_id) AS number_of_friends FROM Friend GROUP BY student_id;	network_1
SELECT T1.name, COUNT(T2.friend_id) AS num_friends FROM Highschooler AS T1 JOIN Friend AS T2 ON T1.ID = T2.student_id GROUP BY T1.ID;	network_1
SELECT T1.name, COUNT(T2.friend_id) AS num_friends FROM Highschooler AS T1 LEFT JOIN Friend AS T2 ON T1.ID = T2.student_id GROUP BY T1.ID, T1.name;	network_1
SELECT T1.name, COUNT(T2.friend_id) AS num_friends FROM Highschooler AS T1 LEFT JOIN Friend AS T2 ON T1.ID = T2.student_id GROUP BY T1.ID, T1.name;	network_1
SELECT T2.name FROM Friend AS T1 JOIN Highschooler AS T2 ON T1.student_id = T2.ID GROUP BY T1.student_id ORDER BY count(T1.friend_id) DESC LIMIT 1;	network_1
SELECT T1.name FROM Highschooler AS T1 JOIN Friend AS T2 ON T1.ID = T2.student_id GROUP BY T1.ID ORDER BY COUNT(T2.friend_id) DESC LIMIT 1;	network_1
SELECT T1.name FROM Highschooler AS T1 JOIN Friend AS T2 ON T1.ID = T2.student_id GROUP BY T1.ID HAVING COUNT(T2.friend_id) >= 3;	network_1
SELECT T1.name FROM Highschooler AS T1 JOIN Friend AS T2 ON T1.ID = T2.student_id GROUP BY T1.ID HAVING COUNT(T2.friend_id) >= 3;	network_1
SELECT DISTINCT T2.name FROM Friend AS T1 JOIN Highschooler AS T2 ON T1.friend_id = T2.ID JOIN Highschooler AS T3 ON T1.student_id = T3.ID WHERE T3.name = 'Kyle';	network_1
SELECT T3.name FROM Highschooler AS T1 JOIN Friend AS T2 ON T1.ID = T2.student_id JOIN Highschooler AS T3 ON T2.friend_id = T3.ID WHERE T1.name = 'Kyle';	network_1
SELECT COUNT(T2.friend_id) FROM Highschooler AS T1 JOIN Friend AS T2 ON T1.ID = T2.student_id WHERE T1.name = 'Kyle';	network_1
SELECT COUNT(friend_id) FROM Friend JOIN Highschooler ON Friend.student_id = Highschooler.ID WHERE Highschooler.name = 'Kyle';	network_1
SELECT ID FROM Highschooler WHERE ID NOT IN (SELECT student_id FROM Friend UNION SELECT friend_id FROM Friend)	network_1
SELECT ID FROM Highschooler EXCEPT SELECT student_id FROM Friend UNION SELECT friend_id FROM Friend;	network_1
SELECT name FROM Highschooler WHERE ID NOT IN (SELECT student_id FROM Friend UNION SELECT friend_id FROM Friend)	network_1
SELECT name FROM Highschooler WHERE ID NOT IN (SELECT student_id FROM Friend UNION SELECT friend_id FROM Friend);	network_1
SELECT ID FROM Highschooler WHERE ID IN (SELECT friend_id FROM Friend) INTERSECT SELECT liked_id FROM Likes;	network_1
SELECT student_id FROM Likes INTERSECT SELECT student_id FROM Friend;	network_1
SELECT DISTINCT H1.name FROM Highschooler H1 JOIN Friend F ON H1.ID = F.student_id JOIN Likes L ON H1.ID = L.liked_id;	network_1
SELECT DISTINCT T1.name FROM Highschooler AS T1 JOIN Friend AS T2 ON T1.ID = T2.student_id JOIN Likes AS T3 ON T1.ID = T3.student_id;	network_1
SELECT student_id, COUNT(liked_id) AS like_count FROM Likes GROUP BY student_id;	network_1
SELECT student_id, COUNT(liked_id) AS like_count FROM Likes GROUP BY student_id;	network_1
SELECT T2.name, COUNT(*) AS number_of_likes FROM Likes AS T1 JOIN Highschooler AS T2 ON T1.student_id = T2.ID GROUP BY T2.name;	network_1
SELECT T1.name, COUNT(T2.liked_id) AS like_count FROM Highschooler AS T1 JOIN Likes AS T2 ON T1.ID = T2.student_id GROUP BY T1.ID, T1.name;	network_1
SELECT T2.name FROM Likes AS T1 JOIN Highschooler AS T2 ON T1.liked_id = T2.ID GROUP BY T1.liked_id ORDER BY count(*) DESC LIMIT 1;	network_1
SELECT T2.name FROM Likes AS T1 JOIN Highschooler AS T2 ON T1.student_id = T2.ID GROUP BY T1.student_id ORDER BY COUNT(T1.liked_id) DESC LIMIT 1;	network_1
SELECT T2.name FROM Likes AS T1 JOIN Highschooler AS T2 ON T1.student_id = T2.ID GROUP BY T1.student_id HAVING COUNT(T1.liked_id) >= 2;	network_1
SELECT T2.name FROM Likes AS T1 JOIN Highschooler AS T2 ON T1.student_id = T2.ID GROUP BY T1.student_id HAVING COUNT(T1.liked_id) >= 2;	network_1
SELECT H.name FROM Highschooler H JOIN Friend F ON H.ID = F.student_id WHERE H.grade >5 GROUP BY H.ID HAVING COUNT(DISTINCT F.friend_id) >= 2;	network_1
SELECT T1.name FROM Highschooler AS T1 JOIN Friend AS T2 ON T1.ID = T2.student_id WHERE T1.grade >5 GROUP BY T1.ID HAVING COUNT(T2.friend_id) >= 2;	network_1
SELECT COUNT(*) FROM Likes AS L JOIN Highschooler AS H ON L.liked_id = H.ID WHERE H.name = "Kyle";	network_1
SELECT COUNT(*) FROM Likes AS L JOIN Highschooler AS H ON L.liked_id = H.ID WHERE H.name = 'Kyle';	network_1
SELECT AVG(T1.grade) FROM Highschooler AS T1 JOIN Friend AS T2 ON T1.ID = T2.student_id;	network_1
SELECT AVG(T1.grade) FROM Highschooler AS T1 JOIN Friend AS T2 ON T1.ID = T2.student_id;	network_1
SELECT MIN(grade) FROM Highschooler WHERE ID NOT IN (SELECT student_id FROM Friend UNION SELECT friend_id FROM Friend)	network_1
SELECT MIN(grade) FROM Highschooler WHERE ID NOT IN (SELECT student_id FROM Friend UNION SELECT friend_id FROM Friend)	network_1
SELECT state FROM Owners INTERSECT SELECT state FROM Professionals;	dog_kennels
SELECT state FROM Owners INTERSECT SELECT state FROM Professionals;	dog_kennels
SELECT AVG(dogs.age) FROM Dogs JOIN Treatments ON Dogs.dog_id = Treatments.dog_id;	dog_kennels
SELECT AVG(dogs.age) FROM Dogs JOIN Treatments ON Dogs.dog_id = Treatments.dog_id;	dog_kennels
SELECT P.professional_id, P.last_name, P.cell_number FROM Professionals P WHERE P.state = 'Indiana' OR P.professional_id IN ( SELECT T.professional_id FROM Treatments T GROUP BY T.professional_id HAVING COUNT(T.treatment_id) > 2 );	dog_kennels
SELECT P.professional_id, P.last_name, P.cell_number FROM Professionals P WHERE P.state = 'Indiana' OR P.professional_id IN ( SELECT T.professional_id FROM Treatments T GROUP BY T.professional_id HAVING COUNT(T.treatment_id) > 2 );	dog_kennels
SELECT name FROM Dogs WHERE dog_id NOT IN ( SELECT dog_id FROM Treatments GROUP BY dog_id HAVING SUM(cost_of_treatment) > 1000 );	dog_kennels
SELECT D.name FROM Dogs D WHERE D.dog_id NOT IN ( SELECT T.dog_id FROM Treatments T GROUP BY T.dog_id HAVING SUM(T.cost_of_treatment) > 1000 );	dog_kennels
SELECT first_name FROM Professionals UNION SELECT first_name FROM Owners EXCEPT SELECT name FROM Dogs	dog_kennels
SELECT first_name FROM Professionals UNION SELECT first_name FROM Owners EXCEPT SELECT name FROM Dogs	dog_kennels
SELECT professional_id, role_code, email_address FROM Professionals WHERE professional_id NOT IN (SELECT professional_id FROM Treatments);	dog_kennels
SELECT professional_id, role_code, email_address FROM Professionals WHERE professional_id NOT IN (SELECT professional_id FROM Treatments);	dog_kennels
SELECT O.owner_id, O.first_name, O.last_name FROM Owners O JOIN Dogs D ON O.owner_id = D.owner_id GROUP BY O.owner_id, O.first_name, O.last_name ORDER BY COUNT(D.dog_id) DESC LIMIT 1;	dog_kennels
SELECT O.owner_id, O.first_name, O.last_name FROM Owners O JOIN Dogs D ON O.owner_id = D.owner_id GROUP BY O.owner_id, O.first_name, O.last_name ORDER BY COUNT(D.dog_id) DESC LIMIT 1;	dog_kennels
SELECT T1.professional_id, T1.role_code, T1.first_name FROM Professionals AS T1 JOIN Treatments AS T2 ON T1.professional_id = T2.professional_id GROUP BY T1.professional_id HAVING COUNT(T2.treatment_id) >= 2;	dog_kennels
SELECT P.professional_id, P.role_code, P.first_name FROM Professionals P JOIN Treatments T ON P.professional_id = T.professional_id GROUP BY P.professional_id, P.role_code, P.first_name HAVING COUNT(T.treatment_id) >= 2;	dog_kennels
SELECT B.breed_name FROM Breeds B JOIN Dogs D ON B.breed_code = D.breed_code GROUP BY B.breed_name ORDER BY COUNT(D.dog_id) DESC LIMIT 1;	dog_kennels
SELECT b.breed_name FROM Dogs d JOIN Breeds b ON d.breed_code = b.breed_code GROUP BY b.breed_name ORDER BY COUNT(d.dog_id) DESC LIMIT 1;	dog_kennels
SELECT O.owner_id, O.last_name FROM Owners O JOIN Dogs D ON O.owner_id = D.owner_id JOIN Treatments T ON D.dog_id = T.dog_id GROUP BY O.owner_id, O.last_name ORDER BY COUNT(T.treatment_id) DESC LIMIT 1;	dog_kennels
SELECT O.owner_id, O.last_name FROM Owners O JOIN Dogs D ON O.owner_id = D.owner_id JOIN Treatments T ON D.dog_id = T.dog_id GROUP BY O.owner_id, O.last_name ORDER BY SUM(T.cost_of_treatment) DESC LIMIT 1;	dog_kennels
SELECT Treatment_Types.treatment_type_description FROM Treatments JOIN Treatment_Types ON Treatments.treatment_type_code = Treatment_Types.treatment_type_code GROUP BY Treatments.treatment_type_code ORDER BY SUM(Treatments.cost_of_treatment) ASC LIMIT 1;	dog_kennels
SELECT Treatment_Types.treatment_type_description FROM Treatments JOIN Treatment_Types ON Treatments.treatment_type_code = Treatment_Types.treatment_type_code GROUP BY Treatments.treatment_type_code ORDER BY SUM(Treatments.cost_of_treatment) ASC LIMIT 1;	dog_kennels
SELECT O.owner_id, O.zip_code FROM Owners O JOIN Dogs D ON O.owner_id = D.dog_id JOIN Treatments T ON D.dog_id = T.dog_id GROUP BY O.owner_id, O.zip_code ORDER BY SUM(T.cost_of_treatment) DESC LIMIT 1;	dog_kennels
SELECT O.owner_id, O.zip_code FROM Owners O JOIN Dogs D ON O.owner_id = D.owner_id JOIN Treatments T ON D.dog_id = T.dog_id GROUP BY O.owner_id, O.zip_code ORDER BY SUM(T.cost_of_treatment) DESC LIMIT 1;	dog_kennels
SELECT T1.professional_id, T1.cell_number FROM Professionals AS T1 JOIN Treatments AS T2 ON T1.professional_id = T2.professional_id GROUP BY T1.professional_id HAVING COUNT(DISTINCT T2.treatment_type_code) >= 2;	dog_kennels
SELECT P.professional_id, P.cell_number FROM Professionals P JOIN Treatments T ON P.professional_id = T.professional_id GROUP BY P.professional_id HAVING COUNT(DISTINCT T.treatment_type_code) >= 2;	dog_kennels
SELECT Professionals.first_name, Professionals.last_name FROM Professionals JOIN Treatments ON Professionals.professional_id = Treatments.professional_id WHERE Treatments.cost_of_treatment < (SELECT AVG(cost_of_treatment) FROM Treatments);	dog_kennels
SELECT DISTINCT P.first_name, P.last_name FROM Professionals P JOIN Treatments T ON P.professional_id = T.professional_id WHERE T.cost_of_treatment < (SELECT AVG(cost_of_treatment) FROM Treatments);	dog_kennels
SELECT T.date_of_treatment, P.first_name FROM Treatments AS T JOIN Professionals AS P ON T.professional_id = P.professional_id;	dog_kennels
SELECT T.date_of_treatment, P.first_name FROM Treatments AS T JOIN Professionals AS P ON T.professional_id = P.professional_id;	dog_kennels
SELECT T1.cost_of_treatment, T2.treatment_type_description FROM Treatments AS T1 JOIN Treatment_Types AS T2 ON T1.treatment_type_code = T2.treatment_type_code;	dog_kennels
SELECT T2.cost_of_treatment, T1.treatment_type_description FROM Treatment_Types AS T1 JOIN Treatments AS T2 ON T1.treatment_type_code = T2.treatment_type_code;	dog_kennels
SELECT O.first_name, O.last_name, S.size_description FROM Owners O JOIN Dogs D ON O.owner_id = D.owner_id JOIN Sizes S ON D.size_code = S.size_code;	dog_kennels
SELECT O.first_name, O.last_name, S.size_description FROM Owners O JOIN Dogs D ON O.owner_id = D.owner_id JOIN Sizes S ON D.size_code = S.size_code;	dog_kennels
SELECT Owners.first_name, Dogs.name FROM Dogs JOIN Owners ON Dogs.owner_id = Owners.owner_id;	dog_kennels
SELECT Owners.first_name, Dogs.name FROM Owners JOIN Dogs ON Owners.owner_id = Dogs.owner_id;	dog_kennels
SELECT D.name, T.date_of_treatment FROM Dogs D JOIN Treatments T ON D.dog_id = T.dog_id JOIN ( SELECT breed_code FROM Dogs GROUP BY breed_code ORDER BY COUNT(*) ASC LIMIT 1 ) RarestBreed ON D.breed_code = RarestBreed.breed_code;	dog_kennels
SELECT D.name, T.date_of_treatment FROM Dogs D JOIN Treatments T ON D.dog_id = T.dog_id WHERE D.breed_code = ( SELECT breed_code FROM Dogs GROUP BY breed_code ORDER BY COUNT(*) ASC LIMIT 1 );	dog_kennels
SELECT O.first_name, D.name FROM Owners AS O JOIN Dogs AS D ON O.owner_id = D.owner_id WHERE O.state = 'Virginia';	dog_kennels
SELECT O.first_name, D.name FROM Owners O JOIN Dogs D ON O.owner_id = D.owner_id WHERE O.state = 'Virginia';	dog_kennels
SELECT DISTINCT D.date_arrived, D.date_departed FROM Dogs D JOIN Treatments T ON D.dog_id = T.dog_id;	dog_kennels
SELECT DISTINCT D.date_arrived, D.date_departed FROM Dogs D JOIN Treatments T ON D.dog_id = T.dog_id;	dog_kennels
SELECT O.last_name FROM Owners O JOIN Dogs D ON O.owner_id = D.owner_id ORDER BY D.date_of_birth DESC LIMIT 1;	dog_kennels
SELECT O.last_name FROM Owners O JOIN Dogs D ON O.owner_id = D.owner_id ORDER BY D.date_of_birth DESC LIMIT 1;	dog_kennels
SELECT email_address FROM Professionals WHERE state = "Hawaii" OR state = "Wisconsin";	dog_kennels
SELECT email_address FROM Professionals WHERE state IN ('Hawaii', 'Wisconsin');	dog_kennels
SELECT date_arrived, date_departed FROM Dogs;	dog_kennels
SELECT date_arrived, date_departed FROM Dogs;	dog_kennels
SELECT COUNT(DISTINCT dog_id) FROM Treatments;	dog_kennels
SELECT COUNT(DISTINCT dog_id) FROM Treatments;	dog_kennels
SELECT COUNT(DISTINCT professional_id) FROM Treatments;	dog_kennels
SELECT COUNT(DISTINCT professional_id) FROM Treatments;	dog_kennels
SELECT role_code, street, city, state FROM Professionals WHERE city LIKE '%West%';	dog_kennels
SELECT role_code, street, city, state FROM Professionals WHERE city LIKE '%West%';	dog_kennels
SELECT first_name, last_name, email_address FROM Owners WHERE state LIKE '%North%';	dog_kennels
SELECT first_name, last_name, email_address FROM Owners WHERE state LIKE '%North%';	dog_kennels
SELECT COUNT(*) FROM Dogs WHERE age < (SELECT AVG(age) FROM Dogs);	dog_kennels
SELECT COUNT(*) FROM Dogs WHERE age < (SELECT AVG(age) FROM Dogs);	dog_kennels
SELECT cost_of_treatment FROM Treatments ORDER BY date_of_treatment DESC LIMIT 1;	dog_kennels
SELECT cost_of_treatment FROM Treatments ORDER BY date_of_treatment DESC LIMIT 1;	dog_kennels
SELECT COUNT(*) FROM Dogs WHERE dog_id NOT IN (SELECT dog_id FROM Treatments);	dog_kennels
SELECT COUNT(*) FROM Dogs WHERE dog_id NOT IN (SELECT dog_id FROM Treatments);	dog_kennels
SELECT COUNT(owner_id) FROM Owners WHERE owner_id NOT IN (SELECT owner_id FROM Dogs);	dog_kennels
SELECT COUNT(owner_id) FROM Owners WHERE owner_id NOT IN (SELECT owner_id FROM Dogs);	dog_kennels
SELECT COUNT(professional_id) FROM Professionals WHERE professional_id NOT IN (SELECT professional_id FROM Treatments);	dog_kennels
SELECT COUNT(*) FROM Professionals WHERE professional_id NOT IN (SELECT professional_id FROM Treatments);	dog_kennels
SELECT name, age, weight FROM Dogs WHERE abandoned_yn = '1';	dog_kennels
SELECT name, age, weight FROM Dogs WHERE abandoned_yn = '1';	dog_kennels
SELECT AVG(age) FROM Dogs;	dog_kennels
SELECT AVG(age) FROM Dogs;	dog_kennels
SELECT MAX(age) FROM Dogs;	dog_kennels
SELECT age FROM Dogs ORDER BY date_of_birth ASC LIMIT 1;	dog_kennels
SELECT charge_type, charge_amount FROM Charges;	dog_kennels
SELECT charge_type, charge_amount FROM Charges;	dog_kennels
SELECT MAX(charge_amount) FROM Charges;	dog_kennels
SELECT charge_amount FROM Charges WHERE charge_type = (SELECT charge_type FROM Charges ORDER BY charge_amount DESC LIMIT 1) LIMIT 1;	dog_kennels
SELECT email_address, cell_number, home_phone FROM Professionals;	dog_kennels
SELECT email_address, cell_number, home_phone FROM Professionals;	dog_kennels
SELECT B.breed_name, S.size_description FROM Breeds B JOIN Sizes S;	dog_kennels
SELECT DISTINCT B.breed_name, S.size_description FROM Dogs D JOIN Breeds B ON D.breed_code = B.breed_code JOIN Sizes S ON D.size_code = S.size_code;	dog_kennels
SELECT Professionals.first_name, Treatment_Types.treatment_type_description FROM Treatments JOIN Professionals ON Treatments.professional_id = Professionals.professional_id JOIN Treatment_Types ON Treatments.treatment_type_code = Treatment_Types.treatment_type_code;	dog_kennels
SELECT Professionals.first_name, Treatment_Types.treatment_type_description FROM Treatments JOIN Professionals ON Treatments.professional_id = Professionals.professional_id JOIN Treatment_Types ON Treatments.treatment_type_code = Treatment_Types.treatment_type_code;	dog_kennels
SELECT COUNT(*) FROM singer;	singer
SELECT COUNT(*) FROM singer;	singer
SELECT Name FROM singer ORDER BY Net_Worth_Millions ASC;	singer
SELECT Name FROM singer ORDER BY Net_Worth_Millions ASC;	singer
SELECT Birth_Year, Citizenship FROM singer;	singer
SELECT Birth_Year, Citizenship FROM singer;	singer
SELECT Name FROM singer WHERE Citizenship != "France";	singer
SELECT Name FROM singer WHERE Citizenship != 'French';	singer
SELECT Name FROM singer WHERE Birth_Year IN (1948, 1949);	singer
SELECT Name FROM singer WHERE Birth_Year IN (1948, 1949);	singer
SELECT Name FROM singer ORDER BY Net_Worth_Millions DESC LIMIT 1;	singer
SELECT Name FROM singer ORDER BY Net_Worth_Millions DESC LIMIT 1;	singer
SELECT Citizenship, COUNT(*) FROM singer GROUP BY Citizenship;	singer
SELECT Citizenship, COUNT(*) FROM singer GROUP BY Citizenship;	singer
SELECT Citizenship FROM singer GROUP BY Citizenship ORDER BY COUNT(*) DESC LIMIT 1;	singer
SELECT Citizenship FROM singer GROUP BY Citizenship ORDER BY COUNT(*) DESC LIMIT 1;	singer
SELECT Citizenship, MAX(Net_Worth_Millions) FROM singer GROUP BY Citizenship;	singer
SELECT Citizenship, MAX(Net_Worth_Millions) FROM singer GROUP BY Citizenship;	singer
SELECT T2.Title, T1.Name FROM singer AS T1 JOIN song AS T2 ON T1.Singer_ID = T2.Singer_ID;	singer
SELECT song.Title, singer.Name FROM song JOIN singer ON song.Singer_ID = singer.Singer_ID;	singer
SELECT DISTINCT T1.Name FROM singer AS T1 JOIN song AS T2 ON T1.Singer_ID = T2.Singer_ID WHERE T2.Sales > 300000;	singer
SELECT DISTINCT T1.Name FROM singer AS T1 JOIN song AS T2 ON T1.Singer_ID = T2.Singer_ID WHERE T2.Sales > 300000;	singer
SELECT s.Name FROM singer s JOIN song so ON s.Singer_ID = so.Singer_ID GROUP BY s.Singer_ID HAVING COUNT(so.Song_ID) > 1;	singer
SELECT T1.Name FROM singer AS T1 JOIN song AS T2 ON T1.Singer_ID = T2.Singer_ID GROUP BY T1.Singer_ID HAVING COUNT(T2.Song_ID) > 1;	singer
SELECT T1.Name, SUM(T2.Sales) AS Total_Sales FROM singer AS T1 JOIN song AS T2 ON T1.Singer_ID = T2.Singer_ID GROUP BY T1.Name;	singer
SELECT singer.Name, SUM(song.Sales) AS Total_Sales FROM singer JOIN song ON singer.Singer_ID = song.Singer_ID GROUP BY singer.Name;	singer
SELECT Name FROM singer WHERE Singer_ID NOT IN (SELECT Singer_ID FROM song)	singer
SELECT Name FROM singer WHERE Singer_ID NOT IN (SELECT Singer_ID FROM song)	singer
SELECT Citizenship FROM singer WHERE Birth_Year <1945 INTERSECT SELECT Citizenship FROM singer WHERE Birth_Year > 1955;	singer
SELECT Citizenship FROM singer WHERE Birth_Year <1945 INTERSECT SELECT Citizenship FROM singer WHERE Birth_Year > 1955;	singer
SELECT count(*) FROM Other_Available_Features;	real_estate_properties
SELECT T2.feature_type_name FROM Other_Available_Features AS T1 JOIN Ref_Feature_Types AS T2 ON T1.feature_type_code = T2.feature_type_code WHERE T1.feature_name = 'AirCon';	real_estate_properties
SELECT DISTINCT T2.property_type_description FROM Properties AS T1 JOIN Ref_Property_Types AS T2 ON T1.property_type_code = T2.property_type_code;	real_estate_properties
SELECT property_name FROM Properties WHERE (property_type_code = 'House' OR (property_type_code = 'Apartment' AND room_count > 1));	real_estate_properties
